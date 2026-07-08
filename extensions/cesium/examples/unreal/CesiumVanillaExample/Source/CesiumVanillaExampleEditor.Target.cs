using UnrealBuildTool;
using System.Collections.Generic;
using System;

public class CesiumVanillaExampleEditorTarget : TargetRules
{
    public CesiumVanillaExampleEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = ResolveBuildSettingsVersion();
        IncludeOrderVersion = ResolveIncludeOrderVersion();
        ExtraModuleNames.AddRange(new List<string>
        {
            "CesiumVanillaExample"
        });
    }

    private static BuildSettingsVersion ResolveBuildSettingsVersion()
    {
        if (Enum.TryParse("V7", out BuildSettingsVersion v7))
        {
            return v7;
        }
        if (Enum.TryParse("V6", out BuildSettingsVersion v6))
        {
            return v6;
        }
        if (Enum.TryParse("V5", out BuildSettingsVersion v5))
        {
            return v5;
        }
        return BuildSettingsVersion.Latest;
    }

    private static EngineIncludeOrderVersion ResolveIncludeOrderVersion()
    {
        if (Enum.TryParse("Unreal5_8", out EngineIncludeOrderVersion unreal58))
        {
            return unreal58;
        }
        if (Enum.TryParse("Unreal5_7", out EngineIncludeOrderVersion unreal57))
        {
            return unreal57;
        }
        if (Enum.TryParse("Unreal5_6", out EngineIncludeOrderVersion unreal56))
        {
            return unreal56;
        }
        return EngineIncludeOrderVersion.Latest;
    }
}
