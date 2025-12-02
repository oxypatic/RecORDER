import asyncio
import sys
import threading
import datetime as dt
import traceback
import json
from urllib.request import urlopen
from os import makedirs
from os import path as os_path
from re import sub
from shutil import move as move_file

import obspython as obs # type: ignore

# Author: oxypatic! (61553947+padiix@users.noreply.github.com)

# Table of capturing video source names
# >>> ONLY PLACE WHERE MODIFICATIONS ARE SAFE FOR YOU TO DO! <<<
SOURCE_NAMES = ["Game Capture", "Window Capture"]
# >>> ONLY PLACE WHERE MODIFICATIONS ARE SAFE FOR YOU TO DO! <<<


class CONST:
    VERSION = "2.1.1"
    PYTHON_VERSION = sys.version_info
    TIME_TO_WAIT = 0.5

class SOURCE_TYPES:
    GAME_CAPTURE = "game_capture"
    WINDOW_CAPTURE = "window_capture"
    DISPLAY_CAPTURE = "monitor_capture"


# Version check

if CONST.PYTHON_VERSION < (3, 11):
    print("Python version < 3.11, correct behaviour is not guaranteed!")


# Values supporting smooth working and fewer calls

file_changed_sh_ref = None


# Utility functions

def log(message):
    print(f"[{dt.datetime.now().isoformat(sep=' ', timespec='seconds')}] {message}")
    
    
def get_latest_release_tag() -> dict | None:
    url = "https://api.github.com/repos/oxypatic/RecORDER/releases/latest"

    try:
        with urlopen(url, timeout=2) as response:
            if response.status == 200:
                data = json.load(response)
                return data.get('tag_name')
    except Exception:
        log("Failed to check updates.")
        log(traceback.format_exc(1))
    return None


def check_updates(current_version: str):
    latest_version = get_latest_release_tag()
    if latest_version and f'{current_version}' != latest_version:
        return True
    return False

def check_updates_callback(props, prop, *args, **kwargs):
    version_check_prop = obs.obs_properties_get(props, "version_info")
    
    if (obs.obs_property_visible(version_check_prop)):
        return True
    
    if check_updates(CONST.VERSION):
        obs.obs_property_set_visible(version_check_prop, True)
        obs.obs_property_set_description(version_check_prop, f"Update available: {get_latest_release_tag()}.\nHead to GitHub for latest version!")
    else:
        obs.obs_property_set_visible(version_check_prop, True)
        obs.obs_property_set_description(version_check_prop, "You have the latest version!")
        
    return True

# CLASSES

class GlobalVariables:
    """Class that holds and allows better control over the Global variables used in this script"""

    def __init__(self):
        # [PROPERTIES]
        self._add_game_title_to_recording_name = None
        self._time_to_wait = 0.5

        # [Related to RECORDING]
        self._is_recording = False
        self._is_replay_active = False
        self._last_recording_path = None
        self._source_uuid = None

    def apply_config(self, add_game_title_to_recording_name: bool, default_folder_name: str):
        self._add_game_title_to_recording_name = add_game_title_to_recording_name
        self._default_recording_name = default_folder_name
        self._game_title = self._default_recording_name
        
    # ---

    @property
    def add_game_title_to_recording_name(self):
        return self._add_game_title_to_recording_name
    
    @add_game_title_to_recording_name.setter
    def add_game_title_to_recording_name(self, value: bool):
        self._add_game_title_to_recording_name = value
    
    @property
    def time_to_wait(self) -> float:
        return self._time_to_wait
    
    @time_to_wait.setter
    def time_to_wait(self, value: float):
        self._time_to_wait = value

    # ---

    @property
    def default_recording_name(self) -> str:
        return self._default_recording_name

    @default_recording_name.setter
    def default_recording_name(self, value: str):
        self._default_recording_name = value
    
    @property
    def is_recording(self) -> bool:
        return self._is_recording
    
    @is_recording.setter
    def is_recording(self, value: bool):
        self._is_recording = value

    @property
    def is_replay_active(self) -> bool:
        return self._is_replay_active
    
    @is_replay_active.setter
    def is_replay_active(self, value: bool):
        self._is_replay_active = value

    @property
    def last_recording(self) -> str | None:
        return self._last_recording_path
    
    @last_recording.setter
    def last_recording(self, value: str | None):
        self._last_recording_path = value
    
    @property
    def game_title(self) -> str:
        return self._game_title

    @game_title.setter
    def game_title(self, value: str):
        self._game_title = remove_unusable_title_characters(value)

    @property
    def source_uuid(self) -> str | None:
        return self._source_uuid

    @source_uuid.setter
    def source_uuid(self, value: str | None):
        self._source_uuid = value

    # ---

    def unload_func(self):
        for key in list(self.__dict__.keys()):
            if key.startswith('_'):
                self.__dict__[key] = None


class MediaFile:
    """Base class for managing media files (recordings and screenshots)"""

    def __init__(self, custom_path: str | None = None, media_type: str = "recording") -> None:
        """Initialize media file with common path handling.
        
        Args:
            custom_path: Optional custom path to file
            media_type: Type of media - 'recording', 'replay', or 'screenshot'
        """
        global globalVariables
        
        self.game_title = globalVariables.game_title
        self.add_title_prefix = globalVariables.add_game_title_to_recording_name
        self.media_type = media_type
        
        # Set custom subfolder name based on media type
        if media_type == "recording":
            self.subfolder_name = None  # No subfolder for recordings
        elif media_type == "replay":
            self.subfolder_name = "Replays"
        elif media_type == "screenshot":
            self.subfolder_name = "Screenshots"
        else:
            self.subfolder_name = None
        
        # Determine file path
        if custom_path:
            self.path = custom_path
        elif media_type == "replay":
            self.path = obs.obs_frontend_get_last_replay()
        elif media_type == "screenshot":
            self.path = obs.obs_frontend_get_last_screenshot()
        else:
            self.path = obs.obs_frontend_get_last_recording()
        
        # Extract directory and filename
        self.dir = os_path.dirname(self.path)
        self.filename = os_path.basename(self.path)
    
    def get_filename(self) -> str:
        """Returns the base file name.
        
        Returns:
            str: name of the file
        """
        return self.filename
    
    def get_new_folder(self) -> str:
        """Returns the target folder path for this media file.
        
        Returns:
            str: path to the target folder
        """
        if self.subfolder_name:
            return os_path.normpath(os_path.join(self.dir, self.game_title, self.subfolder_name))
        else:
            return os_path.normpath(os_path.join(self.dir, self.game_title))
    
    def get_new_filename(self) -> str:
        """Returns the new filename with optional game title prefix.
        
        Returns:
            str: new filename for the file
        """
        if self.add_title_prefix:
            return f"{self.game_title} - {self.get_filename()}"
        else:
            return self.get_filename()
    
    def get_old_path(self) -> str:
        """Returns the original file path.
        
        Returns:
            str: original full path of the file
        """
        return os_path.normpath(os_path.join(self.dir, self.get_filename()))
    
    def get_new_path(self) -> str:
        """Returns the target file path.
        
        Returns:
            str: target full path for the file
        """
        return os_path.normpath(os_path.join(self.get_new_folder(), self.get_new_filename()))
    
    def create_new_folder(self) -> None:
        """Creates the target folder if it doesn't exist."""
        if not os_path.exists(self.get_new_folder()):
            makedirs(self.get_new_folder())


class Recording(MediaFile):
    """Class for handling recording files"""

    def __init__(self, custom_path: str | None = None, is_replay: bool = False) -> None:
        """Create a recording file object.

        Args:
            custom_path (str): Optional path to a recording file
            is_replay (bool): Whether this is a replay buffer recording
        """
        media_type = "replay" if is_replay else "recording"
        super().__init__(custom_path=custom_path, media_type=media_type)


class Screenshot(MediaFile):
    """Class for handling screenshot files"""

    def __init__(self, custom_path: str | None = None) -> None:
        """Create a screenshot file object.

        Args:
            custom_path (str): Optional path to a screenshot file
        """
        super().__init__(custom_path=custom_path, media_type="screenshot")


# ASYNC FUNCTIONS

async def remember_and_move(old_path: str, new_path: str) -> None:
    """Moves the recording to new location using shutil.move() with retries."""
    
    if not os_path.exists(old_path):
        log(f"(Asyncio) File does not exist: {old_path}")
        return
    
    time_to_wait = globalVariables.time_to_wait

    new_dir = None
    max_attempts = 4
    enlarge_timeout_value = 2
    for attempt in range(max_attempts):
        try:
            new_dir = move_file(old_path, new_path)
            break  # Success, exit retry loop
        except Exception as e:
            if attempt < 3:  # Don't print on last attempt (will print final error below)
                log(f"Move attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(time_to_wait)
                time_to_wait *= enlarge_timeout_value
            else:
                log(f"(Asyncio) File move failed after {attempt + 1} attempts: {e}")

    if new_dir is None:
        log("(Asyncio) File was not moved.")
        return

    log("(Asyncio) Done!")
    log(f"(Asyncio) File moved to: {new_dir}")

# HELPER FUNCTIONS

def remove_unusable_title_characters(title: str) -> str:
    # Remove non-alphanumeric characters (ex. ':')
    title = sub(r"[^A-Za-z0-9 ]+", "", title)

    # Remove whitespaces at the end
    title = "".join(title.rstrip())

    # Remove additional whitespaces
    title = " ".join(title.split())

    return title


def move_media_file_asyncio(media_file: MediaFile) -> None:
    """Asynchronously move media file to organized folder."""
    asyncio.run(remember_and_move(media_file.get_old_path(), media_file.get_new_path()))
    
    
# SIGNAL-RELATED

def file_changed_sh(recreate: bool = False) -> None:
    """Signal handler function reacting to automatic file splitting."""
    global file_changed_sh_ref
    if not file_changed_sh_ref:
        output = obs.obs_frontend_get_recording_output()
        try:
            file_changed_sh_ref = obs.obs_output_get_signal_handler(output)
            obs.signal_handler_connect(file_changed_sh_ref, "file_changed", file_changed_cb)
        finally:
            obs.obs_output_release(output)
    else:
        obs.signal_handler_disconnect(file_changed_sh_ref, "file_changed", file_changed_cb)
        if recreate:
            output = obs.obs_frontend_get_recording_output()
            try:
                file_changed_sh_ref = obs.obs_output_get_signal_handler(output)
                obs.signal_handler_connect(file_changed_sh_ref, "file_changed", file_changed_cb)
            finally:
                obs.obs_output_release(output)


def file_changed_cb(calldata: object) -> None:
    """Callback function reacting to the file_changed_sh signal handler function being triggered."""

    log("Recording automatic splitting detected!\n")

    global globalVariables
    
    log("Looking for split file...")
    old_file = globalVariables.last_recording
    new_file = obs.obs_frontend_get_last_recording()
    
    # Store the new file for next split
    globalVariables.last_recording = new_file

    if old_file and old_file != new_file:
        log(f"Moving old recording: {old_file}")
        log(f"New recording detected: {new_file}")
        if globalVariables.game_title == globalVariables.default_recording_name:
            log("Running get_hooked procedure to get current app title...\n")
            check_if_hooked_and_update_title()

        rec = Recording(custom_path=old_file)
        rec.create_new_folder()
        thread = threading.Thread(target=move_media_file_asyncio, args=(rec,), daemon=True)
        thread.start()


def hooked_sh() -> None:
    global SOURCE_NAMES
    global globalVariables
    scene_item_source = None

    log("Checking available sources for a match with source table...")

    current_scene_as_source = obs.obs_frontend_get_current_scene()
    scene = obs.obs_scene_from_source(current_scene_as_source)

    # noinspection PyArgumentList
    #TODO: Can I make this work without SOURCE_NAMES?
    scene_items = obs.obs_scene_enum_items(scene)
    for item in scene_items:
        scene_item_source = obs.obs_sceneitem_get_source(item)
        name = obs.obs_source_get_name(scene_item_source)
        for source in SOURCE_NAMES:
            if name == source:
                globalVariables.source_uuid = obs.obs_source_get_uuid(scene_item_source)
                log("Match found!")
                break

    obs.sceneitem_list_release(scene_items)
    obs.obs_source_release(current_scene_as_source)

    if not globalVariables.source_uuid:
        log("Nothing was found... Are you sure your source is in the 'SOURCE_NAMES' array?")
        return

    # Only proceed if we found a valid source
    if scene_item_source is not None:
        try:
            # log("Fetching the signal handler from the matching source...")
            source_sh_ref = obs.obs_source_get_signal_handler(scene_item_source)
            # log("Connecting the source signal handler to 'hooked' signal...")
            obs.signal_handler_connect(source_sh_ref, "hooked", hooked_cb)
        except Exception as e:
            log(f"Error connecting hooked signal: {e}")
    else:
        log("Warning: No matching source item found.")
    
    
def hooked_cb(calldata: object) -> None:
    global globalVariables

    log("Fetching data from calldata...")

    globalVariables.game_title = obs.calldata_string(calldata, "title")
    log(f"gameTitle: {globalVariables.game_title}")


# EVENTS

def _handle_recording_start() -> None:
    global globalVariables
    
    log("Recording has started...\n")
    log("Reloading the signals!\n")
    if not globalVariables.source_uuid:
        hooked_sh()  # Respond to selected source hooking to a window    
    globalVariables.last_recording = obs.obs_frontend_get_last_recording()
    
    file_changed_sh(recreate=True)  # Respond to splitting the recording (ex. automatic recording split)
    log("Signals reloaded!\n")
    log("Resetting the recording related values...\n")

    globalVariables.is_recording = True
    globalVariables.game_title = globalVariables.default_recording_name

    log(f"Recording started: {'Yes' if globalVariables.is_recording else 'No'}")
    log(f"Current game title: {globalVariables.game_title}")


def _handle_recording_stop() -> None:
    global globalVariables
    
    log("Recording has stopped, moving the last file into right folder...\n")

    if globalVariables.game_title == globalVariables.default_recording_name:
        log("Running get_hooked procedure to get current app title...\n")
        check_if_hooked_and_update_title()

    rec = Recording()
    rec.create_new_folder()
    thread = threading.Thread(target=move_media_file_asyncio, args=(rec,), daemon=True)
    thread.start()

    log("Job's done. The file was moved.")
    globalVariables.last_recording = None
    globalVariables.is_recording = False
    
    
def _handle_replay_buffer_start() -> None:
    global globalVariables
    
    log("Replay buffer has started...\n")

    if not globalVariables.source_uuid:
        log("Reloading the signals!")
        hooked_sh()  # Respond to selected source hooking to a window
        log("Signals reloaded!\n")

    log("Resetting the recording related values...\n")

    globalVariables.is_replay_active = True
    globalVariables.last_recording = obs.obs_frontend_get_last_recording()
    globalVariables.game_title = globalVariables.default_recording_name

    log(f"Replay active? {'Yes' if globalVariables.is_replay_active else 'No'}")
    log(f"CurrentRecording is {globalVariables.last_recording}")
    log(f"Game title set to {globalVariables.game_title}")


def _handle_replay_buffer_save() -> None:
    global globalVariables
    
    log("Saving the Replay Buffer...")

    if globalVariables.game_title == globalVariables.default_recording_name:
        log("Running get_hooked procedure to get current app title...")
        check_if_hooked_and_update_title()

    rec = Recording(is_replay=globalVariables.is_replay_active)
    rec.create_new_folder()
    thread = threading.Thread(target=move_media_file_asyncio, args=(rec,), daemon=True)
    thread.start()


def _handle_replay_buffer_stop() -> None:
    globalVariables.is_replay_active = False
    globalVariables.last_recording = None
    log(f"Replay active? {'Yes' if globalVariables.is_replay_active else 'No'}")


def _handle_screenshot_taken() -> None:
    global globalVariables

    if not globalVariables.source_uuid:
        log("Reloading the signals...")
        hooked_sh()  # Respond to selected source hooking to a window
        log("Signals reloaded.")

    log("Running get_hooked procedure to get current app title...")
    check_if_hooked_and_update_title()

    log("User took the screenshot...")

    screenshot = Screenshot()
    screenshot.create_new_folder()
    thread = threading.Thread(target=move_media_file_asyncio, args=(screenshot,), daemon=True)
    thread.start()

    
def _handle_scene_collection_change() -> None:
    global globalVariables
    
    log("Scene Collection changing detected, freeing globals to avoid issues...")
    globalVariables.unload_func()

    if obs.obs_frontend_recording_active():
        log("Stopping recording...")
        obs.obs_frontend_recording_stop()

    if obs.obs_frontend_replay_buffer_active():
        log("Stopping replay...")
        obs.obs_frontend_replay_buffer_stop()


# EVENT HANDLERS

def _build_event_handlers(enable_replay_organization: bool, enable_screenshot_organization: bool) -> dict:
    handlers = {
        obs.OBS_FRONTEND_EVENT_RECORDING_STARTED: _handle_recording_start,
        obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED: _handle_recording_stop,
        obs.OBS_FRONTEND_EVENT_SCENE_COLLECTION_CHANGING: _handle_scene_collection_change,
    }
    
    if enable_replay_organization:
        handlers[obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STARTED] = _handle_replay_buffer_start
        handlers[obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED] = _handle_replay_buffer_save
        handlers[obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_STOPPED] = _handle_replay_buffer_stop
        
    if enable_screenshot_organization:
        handlers[obs.OBS_FRONTEND_EVENT_SCREENSHOT_TAKEN] = _handle_screenshot_taken
        
    return handlers
          
    
def global_event_handler(event: int) -> None:
    """Single dispatcher for all OBS frontend events"""

    if handler := EVENT_HANDLERS.get(event):
        handler()
        

# PROCEDURES

def check_if_hooked_and_update_title():
    """Function checks if source selected by user is hooked to any window and takes the title of hooked window

    Raises:
        TypeError: Only triggers when sourceUUID is None and causes the title to reset to defaultRecordingName
    """
    global globalVariables

    if globalVariables.source_uuid is None:
        log("Source UUID is empty. Defaulting to 'Manual Recording'")
        globalVariables.game_title = globalVariables.default_recording_name
        return

    calldata = get_hooked(globalVariables.source_uuid)
    log("Checking if source is hooked to any window...")
    if calldata is not None:
        if not gh_is_hooked(calldata):
            obs.calldata_destroy(calldata)
            globalVariables.game_title = globalVariables.default_recording_name
            log("Call data was empty, using default name for un-captured windows...")
            return
        log("Hooked!")
        try:
            globalVariables.game_title = gh_title(calldata)
        except TypeError:
            log("Failed to get title, using default name - restart OBS or captured app.")
            globalVariables.game_title = globalVariables.default_recording_name
        log(f"Current game title: {globalVariables.game_title}")


def get_hooked(uuid: str) -> object:
    source = obs.obs_get_source_by_uuid(uuid)
    cd = obs.calldata_create()
    ph = obs.obs_source_get_proc_handler(source)
    obs.proc_handler_call(ph, "get_hooked", cd)
    obs.obs_source_release(source)
    return cd


def gh_is_hooked(calldata: object) -> bool:
    return obs.calldata_bool(calldata, "hooked")


def gh_title(calldata: object) -> str:
    return obs.calldata_string(calldata, "title")


# OBS FUNCTIONS

def check_updates_press():
    print("Checking for updates...")


def script_load(settings):
    # Loading object of class holding global variables
    global globalVariables
    globalVariables = GlobalVariables()

    # Validate globalVariables is initialized
    if globalVariables is None:
        log("Error: globalVariables not initialized.")
        return

    # Loading in Signals
    file_changed_sh(recreate=True)  # Respond to splitting the recording (ex. automatic recording split)

    # Loading in Frontend events
    obs.obs_frontend_add_event_callback(global_event_handler)
    

def script_defaults(settings):
    obs.obs_data_set_default_string(settings, "default_folder_name_text", "Manual Recording")
    obs.obs_data_set_default_bool(settings, "title_before_bool", False)
    obs.obs_data_set_default_bool(settings, "organize_replay_bool", True)
    obs.obs_data_set_default_bool(settings, "organize_screenshots_bool", True)


def script_update(settings):
    global globalVariables
    global EVENT_HANDLERS

    # Fetching the Settings
    globalVariables.apply_config(obs.obs_data_get_bool(settings, "title_before_bool"), 
                                 obs.obs_data_get_string(settings, "default_folder_name_text"))

    EVENT_HANDLERS = _build_event_handlers(enable_replay_organization = obs.obs_data_get_bool(settings, "organize_replay_bool"),
                                           enable_screenshot_organization = obs.obs_data_get_bool(settings, "organize_screenshots_bool"))
    
    log("(script_update) Updated the settings!\n")


def script_unload():
    # Fetching global variables
    global globalVariables
    global file_changed_sh_ref

    # Clear events
    obs.obs_frontend_remove_event_callback(global_event_handler)

    # Clear global variables
    globalVariables.unload_func()

    # Clear signal for automatic splitting function
    file_changed_sh(recreate=False)
    

def has_video_output(source) -> bool:
    """Check if source has video output capability"""
    flags = obs.obs_source_get_output_flags(source)
    return (flags & obs.OBS_SOURCE_VIDEO) != 0

def is_display_capture(source) -> bool:
    """Check if source is a Display Capture"""
    return obs.obs_source_get_id(source) == SOURCE_TYPES.DISPLAY_CAPTURE
    
    
def script_properties():
    props = obs.obs_properties_create()

    # Default folder name text input
    obs.obs_properties_add_text(
        props, "default_folder_name_text", "Default folder name: ", obs.OBS_TEXT_DEFAULT)

    # Organize replay buffer checkmark
    organize_replay = obs.obs_properties_add_bool(
        props, "organize_replay_bool", "Organize Replay Buffer recordings ")
    obs.obs_property_set_long_description(
        organize_replay,
        "Check the box, if you want to have replays organized into subfolders, uncheck to disable"
    )
    
    # Organize screenshots checkmark
    organize_screenshots = obs.obs_properties_add_bool(
        props, "organize_screenshots_bool", "Organize screenshots ")
    obs.obs_property_set_long_description(
        organize_screenshots,
        "Check the box, if you want to have screenshots organized into subfolders, uncheck to disable"
    )
    
    # Title checkmark
    title_as_prefix = obs.obs_properties_add_bool(
        props, "title_before_bool", "Add game name as a file prefix "
    )
    obs.obs_property_set_long_description(
        title_as_prefix,
        "Check the box, if you want to have title of hooked application appended as a prefix to the recording, else uncheck"
    )

    # Check for updates button
    check_updates = obs.obs_properties_add_button(
        props,
        "check_updates_button",
        "Check for updates",
        check_updates_press
    )
    obs.obs_property_set_modified_callback(check_updates, check_updates_callback)
    
    update_text = obs.obs_properties_add_text(
        props, 
        "version_info",
        "", 
        obs.OBS_TEXT_INFO
    )
    
    obs.obs_property_set_visible(update_text, False)
    
    return props


def script_description():
    return f"""
        <div style="font-size: 40pt; text-align: center;"> RecORDER <i>{CONST.VERSION}</i> </div>
        <hr>
        <div style="font-size: 12pt; text-align: left;">
        Rename and organize media into subfolders!<br>
        <i>Similar to ShadowPlay (GeForce Experience</i>).
        </div>
        <div style="font-size: 12pt; text-align: left; margin-top: 20px; margin-bottom: 20px;">
        Created and maintained by: oxypatic
        </div>
        
        <div style="font-weight: bold; text-decoration: underline; font-size: 12pt; color: red;">
        Important:
        </div>
        <div style="font-size: 11pt; color: red;">
        Make sure your <b>Game Capture/Window Capture</b> source name is inside <b>'SOURCE_NAMES'</b>!
        </div>
        <div style="font-weight: bold; font-size: 12pt; margin-top: 25px;">
        Settings:
        </div>
    """