using UnrealBuildTool;
using System.Collections.Generic;
using System;

public class CesiumVanillaExampleTarget : TargetRules
{
    public CesiumVanillaExampleTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = ResolveBuildSettingsVersion();
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
}
