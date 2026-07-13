using System.Collections;
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Globalization;
using UnityEngine;

// Version marker: this capture harness is aligned to the repo's Unity proof lanes,
// with the example-project file pinned to 6000.6.0b2 and the baseline lane tracked
// separately at 6000.5.0f1.
public sealed class CesiumVisualProofCapture : MonoBehaviour
{
    private const string ManifestFileName = "visual_proof_manifest.json";
    private const string PhaseLogFileName = "player_visual_proof_phase.log";
    private static readonly (string name, Vector3 cameraPosition, float fieldOfView)[] Shots =
    {
        ("overview", new Vector3(0.0f, 4200.0f, 3800.0f), 55.0f),
        ("oblique", new Vector3(4200.0f, 1800.0f, 2600.0f), 45.0f),
        ("close", new Vector3(4300.0f, 800.0f, 1400.0f), 50.0f),
    };
    private static readonly Vector3 CloseLookAt = new Vector3(3600.0f, 400.0f, 1300.0f);

    private static readonly (string name, bool usesCesium)[] Variants =
    {
        ("proxy", false),
        ("cesium", true),
    };

    private Camera _camera;
    private Transform _cameraTransform;
    private string _captureRoot;
    private GameObject _closeMarker;
    private Component _cesiumTileset;
    private bool _cesiumConfigured;
    private bool _cesiumReady;
    private int _cesiumRendererCount;
    private string _cesiumFailure = "";
    private string _cesiumSource = "";

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    private static void Bootstrap()
    {
        Application.runInBackground = true;
        var runner = new GameObject(nameof(CesiumVisualProofCapture));
        UnityEngine.Object.DontDestroyOnLoad(runner);
        runner.AddComponent<CesiumVisualProofCapture>();
    }

    private IEnumerator Start()
    {
        _captureRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "build", "unity", "CesiumVanillaExample", "visual_proof"));
        Directory.CreateDirectory(_captureRoot);

        foreach (var variant in Variants)
        {
            BuildScene(variant.usesCesium);
            yield return new WaitForEndOfFrame();
            if (variant.usesCesium)
            {
                yield return WaitForCesiumContent();
            }

            foreach (var shot in Shots)
            {
                var path = CaptureShot($"{variant.name}_{shot.name}", shot.cameraPosition, shot.fieldOfView);
                yield return new WaitForEndOfFrame();
                yield return WaitForCaptureFile(path);
            }

            TeardownScene();
            yield return new WaitForEndOfFrame();
        }

        yield return new WaitForSecondsRealtime(0.5f);
        WriteManifest();
        Debug.Log($"Cesium visual proof written to {_captureRoot}");
        Application.Quit(0);
    }

    private void BuildScene(bool usesCesium)
    {
        WritePhase("BuildScene begin usesCesium=" + usesCesium);
        var lightObject = new GameObject("VisualProofLight");
        var light = lightObject.AddComponent<Light>();
        light.type = LightType.Directional;
        lightObject.transform.rotation = Quaternion.Euler(-55.0f, 30.0f, 0.0f);

        if (usesCesium)
        {
            TryBuildCesiumEarth();
            return;
        }

        var earth = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        earth.name = "VisualProofEarth";
        earth.transform.localScale = new Vector3(4400.0f, 4400.0f, 4400.0f);
        earth.transform.position = Vector3.zero;
        var earthRenderer = earth.GetComponent<Renderer>();
        if (earthRenderer != null)
        {
            earthRenderer.material = new Material(Shader.Find("Standard"))
            {
                color = new Color(0.12f, 0.32f, 0.68f, 1.0f),
            };
        }

        _closeMarker = GameObject.CreatePrimitive(PrimitiveType.Cube);
        _closeMarker.name = "VisualProofCloseMarker";
        _closeMarker.transform.localScale = new Vector3(700.0f, 300.0f, 300.0f);
        _closeMarker.transform.position = CloseLookAt;
        var closeRenderer = _closeMarker.GetComponent<Renderer>();
        if (closeRenderer != null)
        {
            closeRenderer.material = new Material(Shader.Find("Standard"))
            {
                color = new Color(0.95f, 0.35f, 0.88f, 1.0f),
            };
        }

        var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        cube.name = "VisualProofCube";
        cube.transform.localScale = new Vector3(500.0f, 200.0f, 200.0f);
        cube.transform.position = Vector3.zero;

        var cameraObject = new GameObject("VisualProofCamera");
        _camera = cameraObject.AddComponent<Camera>();
        _camera.clearFlags = CameraClearFlags.SolidColor;
        _camera.backgroundColor = new Color(0.16f, 0.2f, 0.24f, 1.0f);
        _camera.nearClipPlane = 0.1f;
        _camera.farClipPlane = 100000.0f;
        _camera.fieldOfView = 55.0f;
        _cameraTransform = cameraObject.transform;
        WritePhase("BuildScene ready usesCesium=" + usesCesium);
    }

    private bool TryBuildCesiumEarth()
    {
        var url = Environment.GetEnvironmentVariable("CESIUM_3DTILES_URL") ?? "";
        Type georeferenceType = FindType("CesiumForUnity.CesiumGeoreference");
        Type tilesetType = FindType("CesiumForUnity.Cesium3DTileset");
        Type dataSourceType = FindType("CesiumForUnity.CesiumDataSource");
        Type originPlacementType = FindType("CesiumForUnity.CesiumGeoreferenceOriginPlacement");

        if (georeferenceType == null || tilesetType == null || dataSourceType == null)
        {
            Debug.Log("Cesium Unity types were not available; falling back to the proxy earth for this pass");
            return false;
        }

        var georeferenceObject = new GameObject("VisualProofCesiumGeoreference");
        georeferenceObject.transform.position = Vector3.zero;
        var georeference = georeferenceObject.AddComponent(georeferenceType);
        SetEnumProperty(georeference, "originPlacement", originPlacementType, "TrueOrigin");
        SetProperty(georeference, "scale", 0.0345d);
        if (!string.IsNullOrEmpty(url))
        {
            var origin = GetProofEngineOrigin();
            SetProperty(georeference, "ecefX", (double)origin.x);
            SetProperty(georeference, "ecefY", (double)origin.y);
            SetProperty(georeference, "ecefZ", (double)origin.z);
            SetProperty(georeference, "scale", GetProofScale());
            WritePhase($"Cesium proof georeference ecef={origin} scale={GetProofScale():0.###}");
        }

        var tilesetObject = new GameObject("VisualProofCesiumTileset");
        tilesetObject.transform.SetParent(georeferenceObject.transform, false);
        // Cesium starts its native request pipeline from Unity lifecycle
        // callbacks. Configure the source while inactive so FromUrl and the
        // URL are applied before the first load attempt.
        tilesetObject.SetActive(false);
        var tileset = tilesetObject.AddComponent(tilesetType);
        _cesiumTileset = tileset;

        var token = Environment.GetEnvironmentVariable("CESIUM_ION_TOKEN") ??
                    Environment.GetEnvironmentVariable("CESIUM_ION_ACCESS_TOKEN") ??
                    Environment.GetEnvironmentVariable("CESIUMION_TOKEN") ?? "";
        if (!string.IsNullOrEmpty(token))
        {
            SetEnumProperty(tileset, "tilesetSource", dataSourceType, "FromCesiumIon");
            SetProperty(tileset, "ionAssetID", 1L);
            SetProperty(tileset, "ionAccessToken", token);
            var overlayType = FindType("CesiumForUnity.CesiumIonRasterOverlay");
            if (overlayType != null)
            {
                var overlay = tilesetObject.AddComponent(overlayType);
                SetProperty(overlay, "ionAssetID", 2L);
                SetProperty(overlay, "ionAccessToken", token);
            }
            _cesiumConfigured = true;
            _cesiumSource = "ion";
            WritePhase("Cesium configured source=ion terrain_asset=1 imagery_asset=2");
        }
        else if (!string.IsNullOrEmpty(url))
        {
            SetEnumProperty(tileset, "tilesetSource", dataSourceType, "FromUrl");
            SetProperty(tileset, "url", url);
            _cesiumConfigured = true;
            _cesiumSource = "url";
            WritePhase("Cesium configured source=url");
        }
        else
        {
            _cesiumFailure = "CESIUM_ION_TOKEN or CESIUM_3DTILES_URL is required for Cesium-earth proof";
            Debug.LogError(_cesiumFailure);
            WritePhase("CESIUM_CONFIG_ERROR " + _cesiumFailure);
        }

        tilesetObject.SetActive(true);
        // Force one post-activation rebuild for Unity versions whose native
        // partial OnEnable runs before the managed source properties settle.
        InvokePublicMethod(tileset, "RecreateTileset");

        var marker = GameObject.CreatePrimitive(PrimitiveType.Cube);
        marker.name = "VisualProofCesiumCube";
        marker.transform.SetParent(georeferenceObject.transform, false);
        marker.transform.localScale = new Vector3(500.0f, 200.0f, 200.0f);
        marker.transform.localPosition = new Vector3(0.0f, 0.0f, 2500.0f);
        var markerRenderer = marker.GetComponent<Renderer>();
        if (markerRenderer != null)
        {
            markerRenderer.material = new Material(Shader.Find("Standard"))
            {
                color = new Color(0.93f, 0.44f, 0.15f, 1.0f),
            };
        }

        _camera = georeferenceObject.AddComponent<Camera>();
        georeferenceObject.tag = "MainCamera";
        _camera.clearFlags = CameraClearFlags.SolidColor;
        _camera.backgroundColor = new Color(0.16f, 0.2f, 0.24f, 1.0f);
        _camera.nearClipPlane = 0.1f;
        _camera.farClipPlane = 100000.0f;
        _camera.fieldOfView = 55.0f;
        _cameraTransform = _camera.transform;
        RegisterCesiumProofCamera(georeferenceObject, _camera);

        return true;
    }

    private void RegisterCesiumProofCamera(GameObject georeferenceObject, Camera camera)
    {
        Type managerType = FindType("CesiumForUnity.CesiumCameraManager");
        if (managerType == null)
        {
            WritePhase("CESIUM_CAMERA_MANAGER_MISSING");
            return;
        }

        var manager = georeferenceObject.GetComponent(managerType) ?? georeferenceObject.AddComponent(managerType);
        SetProperty(manager, "useMainCamera", false);
        var additionalCameras = managerType.GetProperty("additionalCameras", BindingFlags.Instance | BindingFlags.Public)?.GetValue(manager) as IList;
        if (additionalCameras != null && !additionalCameras.Contains(camera))
        {
            additionalCameras.Add(camera);
            WritePhase("CESIUM_CAMERA_REGISTERED additional=true");
        }
        else
        {
            WritePhase("CESIUM_CAMERA_REGISTERED additional=false");
        }
    }

    private static Vector3 GetProofEngineOrigin()
    {
        var raw = Environment.GetEnvironmentVariable("CESIUM_PROOF_ENGINE_ORIGIN") ?? "";
        var values = raw.Split(',');
        if (values.Length == 3 &&
            float.TryParse(values[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var x) &&
            float.TryParse(values[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var y) &&
            float.TryParse(values[2], NumberStyles.Float, CultureInfo.InvariantCulture, out var z))
        {
            return new Vector3(x, y, z);
        }

        return new Vector3(1215107.761f, -4736682.902f, 4081926.095f);
    }

    private static double GetProofScale()
    {
        var raw = Environment.GetEnvironmentVariable("CESIUM_PROOF_SCALE") ?? "";
        return double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var value) && value > 0.0 ? value : 15.0;
    }

    private IEnumerator WaitForCesiumContent()
    {
        if (!_cesiumConfigured || _cesiumTileset == null)
        {
            _cesiumReady = false;
            yield break;
        }

        var timeout = 30.0f;
        var value = Environment.GetEnvironmentVariable("CESIUM_VISUAL_PROOF_TIMEOUT_SECONDS");
        float.TryParse(value, out timeout);
        if (timeout <= 0.0f) timeout = 30.0f;
        var deadline = Time.realtimeSinceStartup + timeout;
        while (Time.realtimeSinceStartup < deadline)
        {
            var renderers = _cesiumTileset.GetComponentsInChildren<Renderer>(true);
            _cesiumRendererCount = renderers.Length;
            var hasTileChild = _cesiumTileset.transform.childCount > 0;
            if (hasTileChild && _cesiumRendererCount > 0)
            {
                _cesiumReady = true;
                WriteCesiumRendererState(renderers);
                WritePhase($"CESIUM_READY renderer_count={_cesiumRendererCount} child_count={_cesiumTileset.transform.childCount}");
                yield break;
            }
            yield return new WaitForSecondsRealtime(0.25f);
        }

        _cesiumReady = false;
        _cesiumFailure = $"Cesium tiles did not create renderers within {timeout:0.0}s";
        Debug.LogError(_cesiumFailure);
        WritePhase($"CESIUM_NOT_READY renderer_count={_cesiumRendererCount} child_count={_cesiumTileset.transform.childCount}");
    }

    private static Type FindType(string fullName)
    {
        foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            var candidate = assembly.GetType(fullName, false);
            if (candidate != null)
            {
                return candidate;
            }
        }

        return Type.GetType(fullName, false);
    }

    private void WriteCesiumRendererState(Renderer[] renderers)
    {
        for (var i = 0; i < renderers.Length; i++)
        {
            var renderer = renderers[i];
            WritePhase($"CESIUM_RENDERER index={i} name={renderer.name} position={renderer.transform.position} local_scale={renderer.transform.localScale} bounds_center={renderer.bounds.center} bounds_size={renderer.bounds.size} enabled={renderer.enabled}");
        }
    }

    private static void SetProperty(object target, string propertyName, object value)
    {
        if (target == null)
        {
            return;
        }

        var property = target.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
        if (property == null || !property.CanWrite)
        {
            return;
        }

        property.SetValue(target, value);
    }

    private static void SetEnumProperty(object target, string propertyName, Type enumType, string enumValueName)
    {
        if (target == null || enumType == null)
        {
            return;
        }

        var property = target.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
        if (property == null || !property.CanWrite)
        {
            return;
        }

        object enumValue = Enum.Parse(enumType, enumValueName, true);
        property.SetValue(target, enumValue);
    }

    private static void InvokePublicMethod(object target, string methodName)
    {
        if (target == null)
        {
            return;
        }

        var method = target.GetType().GetMethod(methodName, BindingFlags.Instance | BindingFlags.Public);
        method?.Invoke(target, null);
    }

    private void TeardownScene()
    {
        foreach (var root in FindObjectsOfType<GameObject>())
        {
            if (root.name.StartsWith("VisualProof"))
            {
                Destroy(root);
            }
        }
        _closeMarker = null;
        _cesiumTileset = null;
    }

    private static Vector3 GetLookAt(string shotName)
    {
        return shotName.EndsWith("_close") ? CloseLookAt : Vector3.zero;
    }

    private string CaptureShot(string name, Vector3 cameraPosition, float fieldOfView)
    {
        WritePhase($"CaptureShot begin {name}");
        _cameraTransform.position = cameraPosition;
        _camera.fieldOfView = fieldOfView;
        _cameraTransform.LookAt(GetLookAt(name), Vector3.up);

        var path = Path.Combine(_captureRoot, $"{name}.png");
        // Render directly from the proof camera so this works in batch mode
        // without depending on Unity's optional Screen Capture module.
        var width = Mathf.Max(Screen.width, 1280);
        var height = Mathf.Max(Screen.height, 720);
        var previousTarget = _camera.targetTexture;
        var previousActive = RenderTexture.active;
        var target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
        var image = new Texture2D(width, height, TextureFormat.RGB24, false);
        try
        {
            _camera.targetTexture = target;
            _camera.Render();
            RenderTexture.active = target;
            image.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            image.Apply();
            File.WriteAllBytes(path, image.EncodeToPNG());
        }
        finally
        {
            _camera.targetTexture = previousTarget;
            RenderTexture.active = previousActive;
            Destroy(target);
            Destroy(image);
        }
        Debug.Log($"Captured {path}");
        WritePhase($"CaptureShot requested {name}");
        return path;
    }

    private IEnumerator WaitForCaptureFile(string path)
    {
        WritePhase($"WaitForCaptureFile begin {Path.GetFileName(path)}");
        var deadline = Time.realtimeSinceStartup + 10.0f;
        while (!File.Exists(path) && Time.realtimeSinceStartup < deadline)
        {
            yield return new WaitForEndOfFrame();
        }

        if (!File.Exists(path))
        {
            Debug.LogError($"Timed out waiting for captured file {path}");
            WritePhase($"WaitForCaptureFile timeout {Path.GetFileName(path)}");
        }
        else
        {
            WritePhase($"WaitForCaptureFile ready {Path.GetFileName(path)}");
        }
    }

    private void WriteManifest()
    {
        var manifestPath = Path.Combine(_captureRoot, ManifestFileName);
        var capturePaths = Shots.SelectMany(
            shot => Variants.Select(variant => Path.Combine(_captureRoot, $"{variant.name}_{shot.name}.png"))
        ).ToArray();
        var builder = new StringBuilder();
        builder.AppendLine("{");
        builder.AppendLine("  \"schema\": \"cesium.visual_proof_manifest.v1\",");
        builder.AppendLine($"  \"generated_at\": \"{EscapeJson(DateTime.UtcNow.ToString("o"))}\",");
        builder.AppendLine("  \"engine\": \"unity\",");
        builder.AppendLine("  \"host\": \"windows\",");
        builder.AppendLine("  \"native_target\": \"windows\",");
        builder.AppendLine("  \"architecture\": \"x86_64\",");
        builder.AppendLine($"  \"version\": \"{EscapeJson(Application.unityVersion)}\",");
        builder.AppendLine($"  \"project_root\": \"{EscapeJson(Path.GetFullPath(Path.Combine(Application.dataPath, "..")))}\",");
        builder.AppendLine("  \"capture_variants\": [\"proxy\", \"cesium\"],");
        builder.AppendLine($"  \"cesium_configured\": {(_cesiumConfigured ? "true" : "false")},");
        builder.AppendLine($"  \"cesium_source\": \"{EscapeJson(_cesiumSource)}\",");
        builder.AppendLine($"  \"cesium_ready\": {(_cesiumReady ? "true" : "false")},");
        builder.AppendLine($"  \"cesium_renderer_count\": {_cesiumRendererCount},");
        builder.AppendLine($"  \"cesium_failure\": \"{EscapeJson(_cesiumFailure)}\",");
        builder.AppendLine("  \"shot_names\": [\"overview\", \"oblique\", \"close\"],");
        builder.AppendLine("  \"camera_shots\": [");
        for (var i = 0; i < Shots.Length; i++)
        {
            var shot = Shots[i];
            var suffix = i + 1 < Shots.Length ? "," : "";
            builder.AppendLine("    {");
            builder.AppendLine($"      \"name\": \"{EscapeJson(shot.name)}\",");
            builder.AppendLine($"      \"camera_position\": [{shot.cameraPosition.x:0.0###}, {shot.cameraPosition.y:0.0###}, {shot.cameraPosition.z:0.0###}],");
            builder.AppendLine($"      \"look_at\": [{GetLookAt(shot.name).x:0.0###}, {GetLookAt(shot.name).y:0.0###}, {GetLookAt(shot.name).z:0.0###}],");
            builder.AppendLine($"      \"fov_degrees\": {shot.fieldOfView:0.0###}");
            builder.AppendLine($"    }}{suffix}");
        }
        builder.AppendLine("  ],");
        builder.AppendLine("  \"capture_paths\": [");
        for (var i = 0; i < capturePaths.Length; i++)
        {
            var suffix = i + 1 < capturePaths.Length ? "," : "";
            builder.AppendLine($"    \"{EscapeJson(capturePaths[i])}\"{suffix}");
        }
        builder.AppendLine("  ]");
        builder.AppendLine("}");
        File.WriteAllText(manifestPath, builder.ToString());
        Debug.Log($"Wrote visual proof manifest to {manifestPath}");
        WritePhase("WriteManifest complete");
    }

    private void WritePhase(string message)
    {
        try
        {
            var phaseRoot = _captureRoot;
            if (string.IsNullOrEmpty(phaseRoot))
            {
                phaseRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "build", "unity", "CesiumVanillaExample", "visual_proof"));
            }

            Directory.CreateDirectory(phaseRoot);
            var phasePath = Path.Combine(phaseRoot, PhaseLogFileName);
            File.AppendAllText(phasePath, $"[{DateTime.UtcNow:O}] {message}{Environment.NewLine}");
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"Failed to write visual proof phase marker: {ex.Message}");
        }
    }

    private static string EscapeJson(string value)
    {
        return value
            .Replace("\\", "\\\\")
            .Replace("\"", "\\\"");
    }
}
