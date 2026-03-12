"""Submit Cavalry render to Deadline."""

import os
import pyblish.api
from dataclasses import dataclass, field, asdict

from ayon_core.lib import collect_frames
from ayon_deadline import abstract_submit_deadline


# Map file extension to Cavalry CLI --format value
EXT_TO_FORMAT = {
    ".png": "png",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".svg": "svg",
    ".gif": "gif",
    ".apng": "apng",
    ".webm": "webm",
    ".webp": "webp",
    ".mp4": "mp4",
    ".mov": "quicktime",
    ".qt": "quicktime",
}


@dataclass
class CavalryPluginInfo:
    SceneFile: str = field(default=None)
    OutputDirectory: str = field(default=None)
    OutputName: str = field(default=None)
    Format: str = field(default=None)
    Composition: str = field(default=None)


class CavalrySubmitDeadline(abstract_submit_deadline.AbstractSubmitDeadline):
    """Submit Cavalry composition render to Deadline."""

    label = "Submit Cavalry to Deadline"
    order = pyblish.api.IntegratorOrder + 0.1
    hosts = ["cavalry"]
    families = ["render.farm"]
    use_published = True
    targets = ["local"]
    settings_category = "deadline"

    def get_job_info(self, job_info=None):
        job_info.Plugin = "Cavalry"

        if not job_info.Frames:
            frame_range = "{}-{}".format(
                int(round(self._instance.data["frameStart"])),
                int(round(self._instance.data["frameEnd"])),
            )
            job_info.Frames = frame_range

        return job_info

    def get_plugin_info(self):
        plugin_info = CavalryPluginInfo()
        instance = self._instance

        render_path = instance.data["expectedFiles"][0]
        render_dir = os.path.dirname(render_path)
        file_name = os.path.basename(render_path)

        # Derive OutputName and Format from expected path
        # Cavalry CLI outputs: {OutputName}.{frame}.{ext} or similar
        ext = os.path.splitext(file_name)[1].lower()
        plugin_info.Format = EXT_TO_FORMAT.get(ext, "png")

        name_without_ext = os.path.splitext(file_name)[0]
        collected = collect_frames([render_path])
        if collected:
            _, frame = list(collected.items())[0]
            if frame and frame in name_without_ext:
                # Strip frame to get prefix (OutputName)
                # e.g. product_v001.000001.png -> product_v001
                plugin_info.OutputName = name_without_ext.replace(
                    frame, ""
                ).rstrip("._-")
            else:
                plugin_info.OutputName = name_without_ext
        else:
            plugin_info.OutputName = name_without_ext

        plugin_info.SceneFile = self.scene_path
        plugin_info.OutputDirectory = render_dir.replace("\\", "/")
        plugin_info.Composition = instance.data.get("comp_id") or ""

        return asdict(plugin_info)

    def from_published_scene(self, replace_in_path=True):
        """Do not overwrite expected files.

        Use published is set to True, so rendering will be triggered
        from published scene. We do not rename expected file paths.
        """
        return super().from_published_scene(False)
