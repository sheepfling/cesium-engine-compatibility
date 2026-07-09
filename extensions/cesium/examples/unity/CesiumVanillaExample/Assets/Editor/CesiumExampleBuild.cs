using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace CesiumExample
{
    public static class CesiumExampleBuild
    {
        private const string OutputRootName = "build/unity/CesiumVanillaExample";
        private const string GeneratedSceneAssetPath = "Assets/CesiumExampleBuild/Generated/CesiumVanillaExample.unity";

        public static int BuildCurrentTarget()
        {
            return BuildForTarget(EditorUserBuildSettings.activeBuildTarget);
        }

        public static int BuildFromCommandLine()
        {
            if (!TryGetCommandLineArgument("-cesiumBuildTarget", out string buildTarget) ||
                !TryParseBuildTarget(buildTarget, out BuildTarget target))
            {
                Debug.LogError("Missing or unsupported -cesiumBuildTarget argument.");
                return 2;
            }

            return BuildForTarget(target);
        }

        private static int BuildForTarget(BuildTarget target)
        {
            if (!TryGetBuildPaths(target, out string targetName, out string outputPath))
            {
                Debug.LogError($"Unsupported build target: {target}");
                return 1;
            }

            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string scenePath = Path.Combine(projectRoot, GeneratedSceneAssetPath.Replace('/', Path.DirectorySeparatorChar));

            Directory.CreateDirectory(Path.GetDirectoryName(scenePath) ?? projectRoot);
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath) ?? projectRoot);

            try
            {
                var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
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
