import sys
from typing import Awaitable, Optional
import obspython as obs  # type: ignore

# Author: oxypatic! (61553947+padiix@users.noreply.github.com)


class BASE_CONSTANTS:
    VERSION = "3.0"
    PYTHON_VERSION = sys.version_info
    TIME_TO_WAIT = 0.5


class OBS_EVENT_NAMES:
    DEFAULT_NOT_CAPTURED_NAME = "Unknown Game"
    HOOKED_SIGNAL_NAME = "hooked"
    TITLE_CALLDATA_NAME = "title"
    GET_HOOKED_PROCEDURE_NAME = "get_hooked"
    FILE_CHANGED_SIGNAL_NAME = "file_changed"


class SUPPORTED_MEDIAFILE_TYPES:
    RECORDING = "recording"
    REPLAY = "replay"
    SCREENSHOT = "screenshot"


class SUPPORTED_SOURCE_TYPES:
    GAME_CAPTURE = "game_capture"
    WINDOW_CAPTURE = "window_capture"
    DISPLAY_CAPTURE = "monitor_capture"


class AVAILABLE_ORGANIZATION_MODES:
    BASIC = "basic"
    DATE_BASED = "date_based"
    # SCENE_BASED = "scene_based"


# Version check

if BASE_CONSTANTS.PYTHON_VERSION < (3, 11):
    print("Python version < 3.11, correct behaviour is not guaranteed!")


# NEW CODE


## DATA
class RecORDERProperties:
    """
    User-configurable settings that control the customizable script behaviour.

    This class represents what the user can personalize in OBS settings.
    """

    def __init__(
        self,
        game_title_prefix: bool,
        enable_replay_organization: bool,
        enable_screenshot_organization: bool,
        fallback_window_title: str = OBS_EVENT_NAMES.DEFAULT_NOT_CAPTURED_NAME,
        selected_source_uuid: str = None,
        selected_organization_mode: str = "basic",
    ):
        self.fallback_window_title: str = fallback_window_title
        self.selected_source_uuid: str = selected_source_uuid
        self.selected_organization_mode: str = selected_organization_mode

        self.game_title_prefix: bool = game_title_prefix
        self.enable_replay_organization: bool = enable_replay_organization
        self.enable_screenshot_organization: bool = enable_screenshot_organization


class HookState:
    """
    Holds everything we know about the currently hook-able source (like Game Capture/ Window Capture).

    Single source of truth for hook-related state.
    """

    def __init__(self, fallback_window_title: str = OBS_EVENT_NAMES.DEFAULT_NOT_CAPTURED_NAME):
        self.source_uuid: Optional[str] = None
        self.window_title: Optional[str] = None
        self.fallback_window_title: str = fallback_window_title
        self.hooked_signal_handler: Optional[object] = None

    def isSourceDiscovered(self) -> bool:
        """Check if we've sucessfully found and connected to a hook-able source."""
        return self.source_uuid is not None

    def isWindowHooked(self) -> bool:
        """Check if we've captured the game title (not using the default)."""
        return self.window_title is not None and self.window_title != self.fallback_window_title

    def reset(self) -> None:
        """Reset all state to initial values, used when changing scene collections."""
        self.source_uuid = None
        self.window_title = None
        self.hooked_signal_handler = None


class RecordingState:
    """
    Tracks current recording sessions state including the file paths.

    Helps manage recording splits and when to process files.
    """

    def __init__(self):
        self.last_file_path: Optional[str] = None
        self.file_changed_signal_handler: Optional[object] = None

    def reset(self) -> None:
        """Clean up recording state, typically after recording stops."""
        self.last_file_path = None
        self.file_changed_signal_handler = None


class ReplayState:
    """
    Manages replay buffer state, keeping it separate from normal recording.
    """

    def __init__(self):
        self.last_file_path: Optional[str]

    def reset(self) -> None:
        """Clean up replay buffer state."""
        self.last_file_path = None


## HANDLERS

# ============================================================================
# SOURCE DISCOVERY AND MANAGEMENT
# ============================================================================


class HookedHandler:
    """
    Responsible for finding the hook-able source in the current scene and establishing a connection to receive calldata with current hooked windows titles.

    This class knows all the details about navigating OBS's scene hierarchy and signal system.
    """

    def __init__(self, properties: RecORDERProperties, state: HookState):
        self.properties: RecORDERProperties = properties
        self.state: HookState = state

    def connect(self) -> bool:
        """
        Main entry point for connecting to hook-able source.

        Orchestrates the entire connection process and returns whether we were sucessful.
        """

        try:
            source_uuid = self.properties.selected_source_uuid
            found_source = obs.obs_get_source_by_uuid(source_uuid)

            if found_source is None:
                print("[HookedHandler] Could not find relevant source in current scene")
                return False

            self.__establishHookConnection(found_source, source_uuid)
            print(
                f"[HookedHandler] Sucessfully connected to source: {obs.obs_source_get_name(found_source)}"
            )
            return True

        finally:
            obs.obs_source_release(found_source)

    def disconnect(self) -> None:
        """Clean-up signal connection when we're done or switching scene collections."""
        if self.state.hooked_signal_handler is not None:
            obs.signal_handler_disconnect(
                self.state.hooked_signal_handler,
                OBS_EVENT_NAMES.HOOKED_SIGNAL_NAME,
                self.__onWindowHooked,
            )
            self.state.hooked_signal_handler = None

    def __establishHookConnection(self, source: object, source_uuid: str) -> None:
        """Connect the right source to "hooked" signal, so we get notifications whenever it hooks into a new game window."""
        # TODO: Whip up a file creating class, that holds information about scene-to-selected_source info.
        #       It should go to the level of scene collections, to make sure that the user always have settings he chose.
        self.state.source_uuid = source_uuid

        signal_handler = obs.obs_source_get_signal_handler(source)
        obs.signal_handler_connect(
            signal_handler, OBS_EVENT_NAMES.HOOKED_SIGNAL_NAME, self.__onWindowHooked
        )

        self.state.hooked_signal_handler = signal_handler

    def __onWindowHooked(self, calldata: any) -> None:
        """
        Callback which fires whenever hook-able source hooks into a new window.

        It extracts the window title and sanitize it for use as a prefix/folder name.
        """
        try:
            raw_title = obs.calldata_string(calldata, OBS_EVENT_NAMES.TITLE_CALLDATA_NAME)

            if raw_title:
                clean_title = self.__sanitizeTitle(raw_title)
                self.state.window_title = clean_title
                # print(f"[HookedHandler] Hooked window title updated: {clean_title}")

        except Exception as e:
            print(f"[HookedHandler] Failed to extract window title: {e}")

    def __sanitizeTitle(self, title: str) -> str:
        import re

        """Removes characters that might cause problems in file/folder names, keeping only alphanumerics and spaces between words."""

        # Remove non-alphanumeric characters (ex. ':')
        title = re.sub(r"[^A-Za-z0-9 ]+", "", title)

        # Remove whitespaces at the end
        title = title.rstrip()

        # Remove additional whitespaces
        title = " ".join(title.split())

        return title


# ============================================================================
# HOOK-ABLE WINDOW TITLE MANAGEMENT
# ============================================================================


class TitleResolver:
    """
    Responsible for determining the currently captured window.

    This can happen in multiple ways - either through "hooked" callback or by actively querying the source.

    This class encapsulates this logic.
    """

    def __init__(self, state: HookState):
        self.state: HookState = state

    def resolveCurrentTitle(self) -> str:
        """
        Main method of figuring out the window title to use. It tries to get current hooked window title, but falls back to the fallback name if nothing is hooked.

        Called before media file processing to ensure we have the right title.
        """
        if not self.state.isSourceDiscovered():
            print("[TitleResolver] No source configured, using fallback name")
            return self.state.fallback_window_title

        calldata = self.__queryHookStatus()

        if calldata is None:
            print("[TitleResolver] Failed to query source, using fallback name")
            return self.state.fallback_window_title

        try:
            is_hooked = obs.calldata_bool(calldata, OBS_EVENT_NAMES.HOOKED_SIGNAL_NAME)

            if not is_hooked:
                print("[TitleResolver] Source not currently hooked, using fallback name")
                return self.state.fallback_window_title

            raw_title = obs.calldata_string(calldata, OBS_EVENT_NAMES.TITLE_CALLDATA_NAME)

            if raw_title:
                clean_title = self.__sanitizeTitle(raw_title)
                self.state.window_title = clean_title
                # print(f"[TitleResolver] Resolved window title: {clean_title}")
                return clean_title
            else:
                # print("[TitleResolver] No title in hooked source, using default name")
                return self.state.fallback_window_title

        except Exception as e:
            print(f"[TitleResolver] Error extracting title: {e}")
            return self.state.fallback_window_title

        finally:
            obs.calldata_destroy(calldata)

    def getCurrentTitleOrDefault(self) -> str:
        if self.state.isWindowHooked():
            return self.state.window_title
        return self.state.fallback_window_title

    def __queryHookStatus(self) -> Optional[object]:
        """
        Actively asks the hook-able source if it's currently hooked to a window.

        This uses OBS's procedure handler system to make a synchronous query.
        """

        try:
            source = obs.obs_get_source_by_uuid(self.state.source_uuid)

            if source is None:
                return None

            try:
                calldata = obs.calldata_create()
                procedure_handler = obs.obs_source_get_proc_handler(source)
                obs.proc_handler_call(
                    procedure_handler, OBS_EVENT_NAMES.GET_HOOKED_PROCEDURE_NAME, calldata
                )
                return calldata

            finally:
                obs.obs_source_release(source)

        except Exception as e:
            print(f"[TitleResolver] Query failed: {e}")
            return None

    def __sanitizeTitle(self, title: str) -> str:
        """Same sanitation logic as in the HookedHandler"""
        # FIXME: Violates DRY, but hell be damned if I know how to share method between classes for now.
        import re

        title = re.sub(r"[^A-Za-z0-9 ]+", "", title)
        title = title.rstrip()
        title = " ".join(title.split())
        return title


# ============================================================================
# FILE ORGANIZATION
# ============================================================================


class MediaFileOrganizer:
    def __init__(
        self, title_resolver: TitleResolver, organization_mode: str = AVAILABLE_ORGANIZATION_MODES.BASIC
    ):
        self.organization_mode: str = organization_mode
        self.title_resolver: TitleResolver = title_resolver

    def processRecording(self, file_path: str) -> None:
        """Process a recording - determine the window title, create folder stucture (if not created),
        and move the file asynchronously to avoid blocking main OBS thread."""
        game_title = self.title_resolver.resolveCurrentTitle()

        # print(f"[MediaOrganizer] Processing recording: {file_path}")
        # print(f"[MediaOrganizer] Window title: {game_title}")

        self.__organizeFileAsync(file_path, game_title, media_type=SUPPORTED_MEDIAFILE_TYPES.RECORDING)

    def processReplay(self, file_path: str) -> None:
        """Process a saved replay buffer file. Works in similar way to processRecording()"""
        game_title = self.title_resolver.resolveCurrentTitle()

        # print(f"[MediaOrganizer] Processing replay: {file_path}")
        # print(f"[MediaOrganizer] Window title: {game_title}")

        self.__organizeFileAsync(file_path, game_title, media_type=SUPPORTED_MEDIAFILE_TYPES.REPLAY)

    def processScreenshot(self, file_path: str) -> None:
        """Process a screenshot file. Works in similar way to processRecording()"""
        game_title = self.title_resolver.resolveCurrentTitle()

        # print(f"[MediaOrganizer] Processing screenshot: {file_path}")
        # print(f"[MediaOrganizer] Window title: {game_title}")

        self.__organizeFileAsync(file_path, game_title, media_type=SUPPORTED_MEDIAFILE_TYPES.SCREENSHOT)

    def __organizeFileAsync(self, file_path: str, game_title: str, media_type: str) -> None:
        """
        Start a background thread to handle file operations.

        This is critical, because file operations can take time and we can not freeze OBS main thread, because it will interrupt recording/replay.
        """
        import threading

        thread = threading.Thread(
            target=self.__moveFileWorker, args=(file_path, game_title, media_type), daemon=True
        )

        thread.start()

    def __moveFileWorker(self, file_path: str, game_title: str, media_type: str) -> None:
        """The actual worker that runs in a background thread.
        We use asyncio to handle the file operations asynchronously and allows for retries and proper error handling"""
        import asyncio

        try:
            # Create a new path based on game_title and media_type
            target_path = self.__calculateNewPath(file_path, game_title, media_type)

            # Run the async move operation
            asyncio.run(self.__move(file_path, target_path))

            print(f"[MediaOrganizer] Sucessfully moved: {file_path} -> {target_path}")

        except Exception as e:
            print(f"[MediaOrganizer] Failed to move file: {e}")

    def __calculateNewPath(self, file_path: str, game_title: str, media_type: str) -> None:
        """Determine new path for the file based on game title and media type."""
        import os
        from datetime import datetime

        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)

        creation_date_unix = os.path.getctime(file_path)
        creation_date = datetime.fromtimestamp(creation_date_unix).strftime("%y-%m-%d")

        if self.organization_mode == AVAILABLE_ORGANIZATION_MODES.BASIC:
            if media_type == SUPPORTED_MEDIAFILE_TYPES.RECORDING:
                new_directory = os.path.join(directory, game_title)
            else:
                new_directory = os.path.join(directory, game_title, media_type)
        elif self.organization_mode == AVAILABLE_ORGANIZATION_MODES.DATE_BASED:
            if media_type == SUPPORTED_MEDIAFILE_TYPES.RECORDING:
                new_directory = os.path.join(directory, game_title, creation_date)
            else:
                new_directory = os.path.join(directory, game_title, media_type, creation_date)

        return os.path.join(new_directory, filename)

    async def __move(self, path: str, target_path: str) -> Awaitable:
        """Async move method that handles retries and ensures file operation completes succesfully."""
        import os
        import shutil
        import asyncio

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # Retry logic
        await asyncio.sleep(0.1)
        shutil.move(path, target_path)


# ============================================================================
# RECORDING MANAGEMENT
# ============================================================================


class RecordingManager:
    """Manages recording, including handling splits when OBS creates new files based on auto-split functionality."""

    def __init__(self, state: RecordingState, organizer: MediaFileOrganizer):
        self.state: RecordingState = state
        self.organizer: MediaFileOrganizer = organizer
        self._callback_wrapper = self._create_callback_wrapper()

    def start(self) -> None:
        """Called when recording starts."""
        self.state.last_file_path = obs.obs_frontend_get_last_recording()

        self.__setupFileChangeMonitoring()

        print(f"[RecordingManager] Recording started: {self.state.last_file_path}")

    def stop(self) -> None:
        """Called when recording stops. We process the final file and clean-up."""

        if self.state.last_file_path:
            self.organizer.processRecording(self.state.last_file_path)
        else:
            print("[RecordingManager] No recorded file location, CHECK THIS!")

        self.__teardownFileChangeMonitoring()
        self.state.reset()

    def _create_callback_wrapper(self):
        """Fix function for a C wrapper that is the obspython library. Otherwise it will not work."""

        def wrapper(calldata: any) -> None:
            self.onFileChange(calldata)

        return wrapper

    def __setupFileChangeMonitoring(self) -> None:
        """
        Connect output to the "file_changed" signal, which fires on recording splits.

        We disconnect any existing connection first to avoid duplicates.
        """
        self.__teardownFileChangeMonitoring()

        try:
            output = obs.obs_frontend_get_recording_output()
            if output is None:
                print("[RecordingManager] No recording output??? CRITICAL!")
                return

            try:
                signal_handler = obs.obs_output_get_signal_handler(output)

                obs.signal_handler_connect(
                    signal_handler, OBS_EVENT_NAMES.FILE_CHANGED_SIGNAL_NAME, self._callback_wrapper
                )
                self.state.file_changed_signal_handler = signal_handler

                print("[RecordingManager] Split monitoring enabled")

            finally:
                obs.obs_output_release(output)

        except Exception as e:
            print(f"[RecordingManager] Failed to setup split monitoring: {e}")

    def __teardownFileChangeMonitoring(self) -> None:
        """Disconnect from the file_changed signal."""
        if self.state.file_changed_signal_handler is not None:
            obs.signal_handler_disconnect(
                self.state.file_changed_signal_handler,
                OBS_EVENT_NAMES.FILE_CHANGED_SIGNAL_NAME,
                self.onFileChange,
            )
            self.state.file_changed_signal_handler = None

    def onFileChange(self, calldata: any) -> None:
        """Callback firing when OBS splits recording to a new file - Process previous file, change target to new recording file."""
        old_file = self.state.last_file_path
        new_file = obs.obs_frontend_get_last_recording()

        # Update tracking for next split
        self.state.last_file_path = new_file

        # Validate we have a file to process and it's actually diferrent
        if old_file and old_file == new_file:
            return

        # Check current window title at time of split

        current_title = self.organizer.title_resolver.resolveCurrentTitle()

        print(f"[RecordingManager] Window title: {current_title}")
        print(f"[RecordingManager] Split detected - processing: {old_file}")
        self.organizer.processRecording(old_file)


# ============================================================================
# REPLAY BUFFER MANAGEMENT
# ============================================================================


class ReplayManager:
    """Manages replay buffer recordings. Simpler than recording, because we only need to process files when user explicitly saves a replay."""

    def __init__(self, state: ReplayState, organizer: MediaFileOrganizer):
        self.state: ReplayState = state
        self.organizer: MediaFileOrganizer = organizer

    def start(self) -> None:
        """Called when the replay buffer starts."""
        self.state.last_file_path = obs.obs_frontend_get_last_replay()
        print(f"[ReplayManager] Replay Buffer started: {self.state.last_file_path}")

    def stop(self) -> None:
        """Called when the replay buffer stops."""
        self.state.reset()
        print("[ReplayManager] Replay Buffer stopped.")

    def processSavedReplay(self) -> None:
        """Called when user saves a replay. We get the path to the saved file and process it through MediaFileOrganizer."""
        self.state.last_file_path = obs.obs_frontend_get_last_replay()

        if self.state.last_file_path:
            print(f"[ReplayManager] Replay saved: {self.state.last_file_path}")
            self.organizer.processReplay(self.state.last_file_path)


# ============================================================================
# CENTRAL ORCHESTRATOR
# ============================================================================


class RecORDER:
    def __init__(self, properties: RecORDERProperties):
        self.__properties: RecORDERProperties = properties
        self.__hook_state: HookState = HookState(
            fallback_window_title=self.__properties.fallback_window_title
        )
        self.__recording_state: RecordingState = RecordingState()
        self.__replay_state: ReplayState = ReplayState()
        self.hooked_handler: HookedHandler = HookedHandler(
            properties=self.__properties, state=self.__hook_state
        )
        self.title_resolver: TitleResolver = TitleResolver(state=self.__hook_state)
        self.organizer: MediaFileOrganizer = MediaFileOrganizer(
            organization_mode=self.__properties.selected_organization_mode,
            title_resolver=self.title_resolver,
        )
        self.recording_manager: RecordingManager = RecordingManager(
            state=self.__recording_state, organizer=self.organizer
        )
        self.replay_manager: ReplayManager = ReplayManager(
            state=self.__replay_state, organizer=self.organizer
        )
        self.event_handlers = self.__buildEventHandlers()

    def __buildEventHandlers(self) -> dict[int, callable]:
        """Creates a mapping of OBS events to the handler methods. This is where we also decide which features are enabled based on user configuration."""
        handlers = {
            obs.OBS_FRONTEND_EVENT_RECORDING_STARTED: self.__handleRecordingStart,
            obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED: self.__handleRecordingStop,
            obs.OBS_FRONTEND_EVENT_SCENE_COLLECTION_CHANGED: self.__handleSceneCollectionChange,
            # obs.OBS_FRONTEND_EVENT_SCENE_CHANGED: self.__handleSceneChange   #TODO: Implement in future, when we have settings file with mappings of selected sources to scenes and scenes collections
        }

        if self.__properties.enable_replay_organization:
            handlers[obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STARTED] = self.__handleReplayStart
            handlers[obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED] = self.__handleReplaySave
            handlers[obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STOPPED] = self.__handleReplayStop

        if self.__properties.enable_screenshot_organization:
            handlers[obs.OBS_FRONTEND_EVENT_SCREENSHOT_TAKEN] = self.__handleScreenshot

        return handlers

    def dispatchEvent(self, event: int) -> None:
        """Single entry point for all OBS events, called by OBS whenever something happens, this method routes it to the appropriate handler."""
        handler = self.event_handlers.get(event)

        if handler is not None:
            try:
                handler()
            except Exception as e:
                print(f"[RecORDER Core] Error handling event {event}: {e}")

    def __ensureHookedAndConnected(self) -> None:
        """Helper method that ensures we've a hooked window in hook-able source before we start processing any media. Called at the end of each session type."""
        if not self.__hook_state.isSourceDiscovered():
            # print("[RecORDER Core] Discovering hook-able source...")
            self.hooked_handler.connect()

    # ========================================================================
    # EVENT HANDLERS - These are the methods that respond to OBS events
    # ========================================================================

    def __handleRecordingStart(self) -> None:
        """Recording started - init and prepare for splits."""
        # print("[RecORDER Core] Recording started")

        if not self.__hook_state.isSourceDiscovered():
            # print("[RecORDER Core] Discovering hook-able source for upcoming splits.")
            self.hooked_handler.connect()

        self.recording_manager.start()

    def __handleRecordingStop(self) -> None:
        """Recording stopped - finalize and process file"""
        # print("[RecORDER Core] Recording stopped")

        if not self.__hook_state.isWindowHooked():
            # print("[RecORDER Core] Ensuring source is discovered and hooked...")
            self.hooked_handler.connect()

        self.recording_manager.stop()

    def __handleReplayStart(self) -> None:
        """Replay Buffer has started - initialize"""
        # print("[RecORDER Core] Replay Buffer started")
        self.replay_manager.start()

    def __handleReplaySave(self) -> None:
        """User saved a replay - process it"""
        # print("[RecORDER Core] Replay Buffer saved")
        self.__ensureHookedAndConnected()
        self.replay_manager.processSavedReplay()

    def __handleReplayStop(self) -> None:
        """Replay Buffer was stopped - clean up"""
        # print("[RecORDER Core] Replay Buffer stopped")
        self.replay_manager.stop()

    def __handleScreenshot(self) -> None:
        """Screenshot was taken - process it"""
        print("[RecORDER Core] Screenshot taken")
        self.__ensureHookedAndConnected()

        screenshot_path = obs.obs_frontend_get_last_screenshot()
        if screenshot_path:
            self.organizer.processScreenshot(screenshot_path)

    def __handleSceneCollectionChange(self, reuse_for_shutdown: bool = False) -> None:
        """Scene collection was changed - clean up everything, because our source references will be invalid"""
        if not reuse_for_shutdown:
            print("[RecORDER Core] Scene Collection changed - performing cleanup")

        # Save and stop any active recording or replay buffer to ensure clean state
        if obs.obs_frontend_recording_active():
            obs.obs_frontend_recording_stop()
            print("[RecORDER Core] Stopped active recording")

        if obs.obs_frontend_replay_buffer_active():
            obs.obs_frontend_replay_buffer_save()
            obs.obs_frontend_replay_buffer_stop()
            print("[RecORDER Core] Stopped active replay buffer")

        # Disconnect all signal handlers and reset state
        self.hooked_handler.disconnect()
        self.__hook_state.reset()
        self.__recording_state.reset()
        self.__replay_state.reset()

        print("[RecORDER Core] Cleanup complete")

    def shutdown(self) -> None:
        """Called when script is being unloaded. Cleans up all connections and state to prevent memory leaks/ crashes."""
        print("[RecORDER Core] Shutting down")
        self.__handleSceneCollectionChange(True)  # Reuse the cleanup logic


# END - NEW CODE

core: Optional[RecORDER] = None


# Utility functions


def log(message):
    import datetime as dt

    print(f"[{dt.datetime.now().isoformat(sep=' ', timespec='seconds')}] {message}")


def get_latest_release_tag() -> dict | None:
    import json
    import traceback
    from urllib.request import urlopen

    url = "https://api.github.com/repos/oxypatic/RecORDER/releases/latest"

    try:
        with urlopen(url, timeout=2) as response:
            if response.status == 200:
                data = json.load(response)
                return data.get("tag_name")
    except Exception:
        log("Failed to check updates.")
        log(traceback.format_exc(1))
    return None


def check_updates(current_version: str):
    latest_version = get_latest_release_tag()
    if latest_version and f"{current_version}" != latest_version:
        return True
    return False


def check_updates_callback(props, prop, *args, **kwargs):
    version_check_prop = obs.obs_properties_get(props, "version_info")

    if obs.obs_property_visible(version_check_prop):
        obs.obs_property_set_visible(version_check_prop, False)
        return True

    if check_updates(BASE_CONSTANTS.VERSION):
        obs.obs_property_set_visible(version_check_prop, True)
        obs.obs_property_set_description(
            version_check_prop,
            f"Update available: {get_latest_release_tag()}\nHead to GitHub for latest version!",
        )
    else:
        obs.obs_property_set_visible(version_check_prop, True)
        obs.obs_property_set_description(version_check_prop, "You have the latest version!")

    return True


# OBS FUNCTIONS


def check_updates_press():
    print("Checking for updates...")


def frontend_event_callback(event):
    global core

    if core is not None:
        core.dispatchEvent(event)


def script_update(settings):
    global core

    if core is not None:
        core.shutdown()

    properties = RecORDERProperties(
        selected_source_uuid=obs.obs_data_get_string(settings, "source_selector"),
        selected_organization_mode=obs.obs_data_get_string(settings, name="organization_mode"),
        game_title_prefix=obs.obs_data_get_bool(settings, "title_as_prefix"),
        enable_replay_organization=obs.obs_data_get_bool(settings, "enable_replay_organization"),
        enable_screenshot_organization=obs.obs_data_get_bool(
            settings, "enable_screenshot_organization"
        ),
        fallback_window_title=obs.obs_data_get_string(settings, "fallback_window_title"),
    )

    core = RecORDER(properties)

    obs.obs_frontend_add_event_callback(frontend_event_callback)

    print("[RecORDER] Configuration updated and orchestrator initialized!")


def script_defaults(settings):
    obs.obs_data_set_default_string(settings, "fallback_window_title", "Any Recording")
    obs.obs_data_set_default_string(settings, "organization_mode", "basic")
    obs.obs_data_set_default_bool(settings, "title_as_prefix", False)
    obs.obs_data_set_default_bool(settings, "enable_replay_organization", True)
    obs.obs_data_set_default_bool(settings, "enable_screenshot_organization", True)


def script_unload():
    global core

    if core is not None:
        core.shutdown()
        core = None

    obs.obs_frontend_remove_event_callback(frontend_event_callback)
    print("[RecORDER] Script unloaded sucessfully!")


def has_video_output(source) -> bool:
    """Check if source has video output capability"""
    flags = obs.obs_source_get_output_flags(source)
    return (flags & obs.OBS_SOURCE_VIDEO) != 0


def is_display_capture(source) -> bool:
    """Check if source is a Display Capture"""
    return obs.obs_source_get_id(source) == SUPPORTED_SOURCE_TYPES.DISPLAY_CAPTURE


def populate_source_selector(source_selector):
    """Dynamically populate source selector with hookable sources from the current scene."""
    try:
        current_scene_source = obs.obs_frontend_get_current_scene()
        if current_scene_source is None:
            obs.obs_property_list_add_string(source_selector, "No active scene", "")
            return

        try:
            current_scene = obs.obs_scene_from_source(current_scene_source)
            scene_items = obs.obs_scene_enum_items(current_scene)

            found_any = False
            for item in scene_items:
                source = obs.obs_sceneitem_get_source(item)
                source_name = obs.obs_source_get_name(source)
                source_uuid = obs.obs_source_get_uuid(source)

                # Only add sources with video ouput
                if has_video_output(source):
                    # Check if the source is a display capture - if it is, then it DOES NOT have a hook events we need (since it's hooking to a display, not window)
                    if is_display_capture(source):
                        obs.obs_property_list_add_string(
                            source_selector, f"{source_name} [Not supported!]", source_uuid
                        )
                    else:
                        obs.obs_property_list_add_string(source_selector, source_name, source_uuid)
                    found_any = True

            if not found_any:
                obs.obs_property_list_add_string(source_selector, "No hookable sources found", "")

        finally:
            obs.obs_source_release(current_scene_source)

    except Exception as e:
        print(f"[script_properties] Failed to populate source selector: {e}")
        obs.obs_property_list_add_string(source_selector, "Error loading sources", "")


def populate_organization_mode(organization_mode):
    obs.obs_property_list_add_string(organization_mode, "Basic", AVAILABLE_ORGANIZATION_MODES.BASIC)
    obs.obs_property_list_add_string(
        organization_mode, "Group by Date", AVAILABLE_ORGANIZATION_MODES.DATE_BASED
    )
    # obs.obs_property_list_add_string(organization_mode, "Scene-based", "scene_based")


def script_properties():
    props = obs.obs_properties_create()

    # Default folder name text input
    obs.obs_properties_add_text(
        props, "fallback_window_title", "Fallback folder name: ", obs.OBS_TEXT_DEFAULT
    )

    # Source selecting property for easier configuration for user
    # IDEA: Make the script remember on which scene was which source picked to ease the use of script!
    source_selector = obs.obs_properties_add_list(
        props,
        "source_selector",
        "Monitored source: ",
        obs.OBS_COMBO_TYPE_LIST,
        obs.OBS_COMBO_FORMAT_STRING,
    )
    populate_source_selector(source_selector)

    # Organization modes for user customization of sorting
    organization_mode = obs.obs_properties_add_list(
        props,
        "organization_mode",
        "Organization mode: ",
        obs.OBS_COMBO_TYPE_LIST,
        obs.OBS_COMBO_FORMAT_STRING,
    )
    populate_organization_mode(organization_mode)

    # Organize replay buffer checkmark
    organize_replay = obs.obs_properties_add_bool(
        props, "enable_replay_organization", "Organize Replay Buffer recordings "
    )
    obs.obs_property_set_long_description(
        organize_replay,
        "Check the box, if you want to have replays organized into subfolders, uncheck to disable",
    )

    # Organize screenshots checkmark
    organize_screenshots = obs.obs_properties_add_bool(
        props, "enable_screenshot_organization", "Organize screenshots "
    )
    obs.obs_property_set_long_description(
        organize_screenshots,
        "Check the box, if you want to have screenshots organized into subfolders, uncheck to disable",
    )

    # Title checkmark
    title_as_prefix = obs.obs_properties_add_bool(
        props, "title_as_prefix", "Add game name as a file prefix "
    )
    obs.obs_property_set_long_description(
        title_as_prefix,
        "Check the box, if you want to have title of hooked application appended as a prefix to the recording, else uncheck",
    )

    # Check for updates button
    check_updates = obs.obs_properties_add_button(
        props, "check_updates_button", "Check for updates", check_updates_press
    )
    obs.obs_property_set_modified_callback(check_updates, check_updates_callback)

    update_text = obs.obs_properties_add_text(props, "version_info", "", obs.OBS_TEXT_INFO)

    obs.obs_property_set_visible(update_text, False)

    return props


def script_description():
    return f"""
        <div style="font-size: 40pt; text-align: center;"> RecORDER <i>{BASE_CONSTANTS.VERSION}</i> </div>
        <hr>
        <div style="font-size: 12pt; text-align: left;">
        Rename and organize media into subfolders!<br>
        <i>Similar to ShadowPlay (GeForce Experience</i>).
        </div>
        <div style="font-size: 12pt; text-align: left; margin-top: 20px; margin-bottom: 20px;">
        Created and maintained by: oxypatic
        </div>
        
        <div style="font-weight: bold; font-size: 12pt; margin-top: 25px;">
        Settings:
        </div>
    """
