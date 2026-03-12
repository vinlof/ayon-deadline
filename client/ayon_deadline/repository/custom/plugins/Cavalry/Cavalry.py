#!/usr/bin/env python3

from __future__ import absolute_import
import sys

from System.Diagnostics import ProcessPriorityClass

from Deadline.Plugins import DeadlinePlugin, PluginType
from Deadline.Scripting import RepositoryUtils, SystemUtils

from FranticX.Processes import ManagedProcess

CAVALRY_EXIT_CODES = {
    200: "Sign in failed. The licence server may be unreachable.",
    201: "Sign in failed due to empty password field.",
    202: "Licence is invalid. Sign in with 'cavalry-cli auth' on the Worker.",
    203: "Licence is invalid. An Enterprise licence is required for CLI rendering.",
    204: "Could not load the Scene file.",
    205: "Render Queue Item does not exist.",
    206: "Validate licence error. Could not save a licence file to disk.",
}


def GetDeadlinePlugin():
    return CavalryPlugin()


def CleanupDeadlinePlugin(deadlinePlugin):
    deadlinePlugin.Cleanup()


class CavalryPlugin(DeadlinePlugin):
    Process = None

    def __init__(self):
        if sys.version_info.major == 3:
            super().__init__()
        self.InitializeProcessCallback += self.InitializeProcess
        self.StartJobCallback += self.StartJob
        self.RenderTasksCallback += self.RenderTasks
        self.EndJobCallback += self.EndJob

    def Cleanup(self):
        del self.InitializeProcessCallback
        del self.StartJobCallback
        del self.RenderTasksCallback
        del self.EndJobCallback

        if self.Process:
            self.Process.Cleanup()
            del self.Process

    def InitializeProcess(self):
        self.SingleFramesOnly = False
        self.PluginType = PluginType.Advanced

    def StartJob(self):
        sceneFile = self.GetPluginInfoEntryWithDefault(
            "SceneFile", self.GetDataFilename()
        )
        sceneFile = RepositoryUtils.CheckPathMapping(sceneFile)

        self.LogInfo("Cavalry Job Settings:")
        self.LogInfo("  Scene File: %s" % sceneFile)
        self.LogInfo(
            "  Format: %s"
            % self.GetPluginInfoEntryWithDefault("Format", "png")
        )
        self.LogInfo(
            "  Output Directory: %s"
            % self.GetPluginInfoEntryWithDefault("OutputDirectory", "")
        )
        self.LogInfo(
            "  Output Name: %s"
            % self.GetPluginInfoEntryWithDefault("OutputName", "")
        )

        composition = self.GetPluginInfoEntryWithDefault("Composition", "")
        if composition:
            self.LogInfo("  Composition: %s" % composition)

    def RenderTasks(self):
        self.Process = CavalryProcess(self)
        self.RunManagedProcess(self.Process)

    def EndJob(self):
        self.LogInfo("Cavalry job complete")


class CavalryProcess(ManagedProcess):
    deadlinePlugin = None

    def __init__(self, deadlinePlugin):
        if sys.version_info.major == 3:
            super().__init__()
        self.deadlinePlugin = deadlinePlugin

        self.InitializeProcessCallback += self.InitializeProcess
        self.RenderExecutableCallback += self.RenderExecutable
        self.RenderArgumentCallback += self.RenderArgument

    def Cleanup(self):
        for stdoutHandler in self.StdoutHandlers:
            del stdoutHandler.HandleCallback

        del self.InitializeProcessCallback
        del self.RenderExecutableCallback
        del self.RenderArgumentCallback

    def InitializeProcess(self):
        self.ProcessPriority = ProcessPriorityClass.BelowNormal
        self.UseProcessTree = True
        self.StdoutHandling = True
        self.PopupHandling = True
        self.HandleQtPopups = True
        self.HandleWindows10Popups = True

        self.deadlinePlugin.SetProcessEnvironmentVariable(
            "QT_USE_NATIVE_WINDOWS", "1"
        )
        self.PressEnterDuringRender = True

        self.AddPopupHandler(".*cavalry.*", "Okay")
        self.AddPopupHandler(".*Cavalry.*", "Okay")
        self.AddPopupHandler(".*cavalry.*", "OK")
        self.AddPopupHandler(".*Cavalry.*", "OK")

        # Cavalry log format: [HH:MM:SS.mmm level   ] message
        self.AddStdoutHandlerCallback(
            ".*\\[.*error.*\\].*"
        ).HandleCallback += self.HandleStdoutError
        self.AddStdoutHandlerCallback(
            ".*\\[.*warn.*\\].*"
        ).HandleCallback += self.HandleStdoutWarning
        self.AddStdoutHandlerCallback(
            ".*\\[.*info.*\\].*"
        ).HandleCallback += self.HandleStdoutInfo

    def RenderExecutable(self):
        return self.deadlinePlugin.GetRenderExecutable(
            "Cavalry_RenderExecutable", "Cavalry"
        )

    def RenderArgument(self):
        sceneFile = self.deadlinePlugin.GetPluginInfoEntryWithDefault(
            "SceneFile", self.deadlinePlugin.GetDataFilename()
        )
        sceneFile = RepositoryUtils.CheckPathMapping(sceneFile)

        if SystemUtils.IsRunningOnWindows():
            sceneFile = sceneFile.replace("/", "\\")
            if sceneFile.startswith("\\") and not sceneFile.startswith("\\\\"):
                sceneFile = "\\" + sceneFile
        else:
            sceneFile = sceneFile.replace("\\", "/")

        arguments = 'render "%s"' % sceneFile

        arguments += " -s %d -e %d" % (
            self.deadlinePlugin.GetStartFrame(),
            self.deadlinePlugin.GetEndFrame(),
        )

        outputDir = self.deadlinePlugin.GetPluginInfoEntryWithDefault(
            "OutputDirectory", ""
        )
        if outputDir:
            outputDir = RepositoryUtils.CheckPathMapping(outputDir)
            if SystemUtils.IsRunningOnWindows():
                outputDir = outputDir.replace("/", "\\")
            else:
                outputDir = outputDir.replace("\\", "/")
            arguments += ' -d "%s"' % outputDir

        outputName = self.deadlinePlugin.GetPluginInfoEntryWithDefault(
            "OutputName", ""
        )
        if outputName:
            arguments += ' -n "%s"' % outputName

        renderFormat = self.deadlinePlugin.GetPluginInfoEntryWithDefault(
            "Format", "png"
        )
        if renderFormat:
            arguments += " --format %s" % renderFormat

        composition = self.deadlinePlugin.GetPluginInfoEntryWithDefault(
            "Composition", ""
        )
        if composition:
            arguments += " --composition %s" % composition

        self.deadlinePlugin.LogInfo("Render arguments: %s" % arguments)
        return arguments

    def HandleStdoutError(self):
        self.deadlinePlugin.LogWarning(self.GetRegexMatch(0))

    def HandleStdoutWarning(self):
        self.deadlinePlugin.LogWarning(self.GetRegexMatch(0))

    def HandleStdoutInfo(self):
        self.deadlinePlugin.LogInfo(self.GetRegexMatch(0))
