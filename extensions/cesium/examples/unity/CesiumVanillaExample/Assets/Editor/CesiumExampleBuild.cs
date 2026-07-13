using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using CesiumForUnity;

namespace CesiumExample
{
    public static class CesiumExampleBuild
    {
        private const string OutputRootName = "build/unity/CesiumVanillaExample";
        private const string GeneratedSceneAssetPath = "Assets/CesiumExampleBuild/Generated/CesiumVanillaExample.unity";

        private readonly struct ShotPose
        {
            public ShotPose(Vector3 cameraPosition, Vector3 lookAt, float fieldOfView)
            {
                CameraPosition = cameraPosition;
                LookAt = lookAt;
                FieldOfView = fieldOfView;
            }

            public Vector3 CameraPosition { get; }
            public Vector3 LookAt { get; }
            public float FieldOfView { get; }
        }

        private static readonly IReadOnlyDictionary<string, ShotPose> ShotPoses = new Dictionary<string, ShotPose>(StringComparer.OrdinalIgnoreCase)
        {
            ["overview"] = new ShotPose(new Vector3(0.0f, 4200.0f, 3800.0f), Vector3.zero, 55.0f),
            ["oblique"] = new ShotPose(new Vector3(4200.0f, 1800.0f, 2600.0f), Vector3.zero, 45.0f),
            ["close"] = new ShotPose(new Vector3(4300.0f, 800.0f, 1400.0f), new Vector3(3600.0f, 400.0f, 1300.0f), 50.0f),
        };

        public static int BuildCurrentTarget()
        {
            return BuildForTarget(EditorUserBuildSettings.activeBuildTarget, "overview");
        }

        public static int BuildFromCommandLine()
        {
            if (!TryGetCommandLineArgument("-cesiumBuildTarget", out string buildTarget) ||
                !TryParseBuildTarget(buildTarget, out BuildTarget target))
            {
                Debug.LogError("Missing or unsupported -cesiumBuildTarget argument.");
                EditorApplication.Exit(2);
                return 2;
            }

            string shot = TryGetCommandLineArgument("-cesiumShot", out string requestedShot) ? requestedShot : "overview";
            int exitCode = BuildForTarget(target, shot);
            EditorApplication.Exit(exitCode);
            return exitCode;
        }

        private static int BuildForTarget(BuildTarget target, string shotName)
        {
            if (!TryGetBuildPaths(target, out string targetName, out string outputPath))
            {
                Debug.LogError($"Unsupported build target: {target}");
                return 1;
            }

            if (!ShotPoses.TryGetValue(shotName ?? string.Empty, out ShotPose shotPose))
            {
                Debug.LogWarning($"Unknown -cesiumShot '{shotName}', falling back to overview.");
                shotPose = ShotPoses["overview"];
                shotName = "overview";
            }

            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string scenePath = Path.Combine(projectRoot, GeneratedSceneAssetPath.Replace('/', Path.DirectorySeparatorChar));

            Directory.CreateDirectory(Path.GetDirectoryName(scenePath) ?? projectRoot);
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath) ?? projectRoot);

            try
            {
                var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
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

                var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
                cube.name = "VisualProofCube";
                cube.transform.localScale = new Vector3(500.0f, 200.0f, 200.0f);
                cube.transform.position = Vector3.zero;

                var camera = Camera.main;
                if (camera != null)
                {
                    camera.fieldOfView = shotPose.FieldOfView;
                    camera.transform.position = shotPose.CameraPosition;
                    camera.transform.LookAt(shotPose.LookAt, Vector3.up);
                }
                Debug.Log($"Configured visual proof shot '{shotName}' for {targetName}.");
                if (!EditorSceneManager.SaveScene(scene, scenePath))
                {
                    Debug.LogError($"Failed to save generated scene at {scenePath}");
                    return 1;
                }

                var buildOptions = new BuildPlayerOptions
                {
                    scenes = new[] { GeneratedSceneAssetPath },
                    locationPathName = outputPath,
                    targetGroup = BuildTargetGroup.Standalone,
                    target = target,
                };

                Debug.Log($"Building Cesium example for {targetName} to {outputPath}");
                if (Environment.GetEnvironmentVariable("CESIUM_BUILD_NATIVE_BEFORE_PLAYER") == "1")
                {
                    CompileCesiumForUnityNative.BuildNativeLibrariesForProof(target);
                }
                BuildReport report = BuildPipeline.BuildPlayer(buildOptions);
                if (report.summary.result != BuildResult.Succeeded)
                {
                    Debug.LogError(
                        $"Build failed for {targetName}: {report.summary.result} ({report.summary.totalErrors} errors, {report.summary.totalWarnings} warnings)");
                    return 1;
                }

                Debug.Log(
                    $"Build succeeded for {targetName}: {report.summary.totalSize} bytes");
                return 0;
            }
            finally
            {
                AssetDatabase.DeleteAsset(GeneratedSceneAssetPath);
                AssetDatabase.Refresh();
            }
        }

        private static bool TryParseBuildTarget(string value, out BuildTarget target)
        {
            switch ((value ?? string.Empty).Trim().ToLowerInvariant())
            {
                case "windows":
                case "standalonewindows64":
                    target = BuildTarget.StandaloneWindows64;
                    return true;
                case "linux":
                case "standalonelinux64":
                    target = BuildTarget.StandaloneLinux64;
                    return true;
                case "mac":
                case "osx":
                case "standaloneosx":
                    target = BuildTarget.StandaloneOSX;
                    return true;
                default:
                    target = BuildTarget.NoTarget;
                return false;
            }
        }

        private static bool TryGetCommandLineArgument(string name, out string value)
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                {
                    value = args[i + 1];
                    return true;
                }
            }

            value = string.Empty;
            return false;
        }

        private static bool TryGetBuildPaths(BuildTarget target, out string targetName, out string outputPath)
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string outputRoot = Path.Combine(projectRoot, OutputRootName);

            if (target == BuildTarget.StandaloneWindows64)
            {
                targetName = "windows";
                outputPath = Path.Combine(outputRoot, targetName, "CesiumVanillaExample.exe");
                return true;
            }

            if (target == BuildTarget.StandaloneLinux64)
            {
                targetName = "linux";
                outputPath = Path.Combine(outputRoot, targetName, "CesiumVanillaExample.x86_64");
                return true;
            }

            if (target == BuildTarget.StandaloneOSX)
            {
                targetName = "mac";
                outputPath = Path.Combine(outputRoot, targetName, "CesiumVanillaExample.app");
                return true;
            }

            targetName = target.ToString();
            outputPath = string.Empty;
            return false;
        }
    }
}
