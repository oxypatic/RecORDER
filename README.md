![Logo](https://github.com/user-attachments/assets/273b1b70-aa5a-43c3-a669-2cf8704adf18)


<div align="right">
   <picture> 
      <img src="https://img.shields.io/badge/version-2.1-11">
   </picture>
   <picture> 
      <img src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=fff">
   </picture>
   <picture>
      <img src="https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black">
   </picture>
   <picture>
      <img src="https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=F0F0F0">
   </picture>
   <picture>
      <img src="https://custom-icon-badges.demolab.com/badge/Windows-0078D6?logo=windows11&logoColor=white">
   </picture>
</div>

## Table of Content
* [What does this script does?](https://github.com/padiix/RecORDER?tab=readme-ov-file#what-does-this-script-does)
* [Features of the script](https://github.com/padiix/RecORDER?tab=readme-ov-file#features-of-the-script)
* [What do I need to do to make it work?](https://github.com/padiix/RecORDER?tab=readme-ov-file#what-do-i-need-to-do-to-make-it-work)
* [FAQ](https://github.com/padiix/RecORDER?tab=readme-ov-file#faq)

## What does this script do?
The script recreates the organization of NVIDIA Shadow Play, <br>which placed all media captured while playing specific game into folder called after the game.

## Requirements
> [!NOTE]  
> This script is designed for ease of use and should work on all Operating Systems

* Script only works with OBS in version 29.0.0 or higher
* Script requires only a **Python 3.11 version** or higher
> [!INFO]
> (**3.12** is the highest the OBS 31.0.3 supports for now)
> [Possibly outdated information]
   * No need for tkinter or anything additionally, minimal python works

## Features of the script
### Main behaviour:
- __Organizes recordings__ in folders called after captured Game/Window
- __Reacts to splitting of recordings__ and actively moves all the splits to relevant folder

### Customizable features:
- __Fallback folder name__ (_the folder to which media will be organized if it cannot find window title_)
- __Organization mode__ (_decide how you want your media organized_)
- __Organization of Replay Buffer recordings__ by RecORDER
- __Organization of screenshots__ by RecORDER

### Other features:
- __Verbose logs of the script__ 
   - View important debug information when checking `Script Logs`
- __Check for updates button__
   - Quickly check if RecORDER have any new updates for you!


## What do I need to do to make it work?
First things first!
1. Install Python - a version [3.11](https://www.python.org/downloads/release/python-31114/) will work, but you can use newer one - [3.12](https://www.python.org/downloads/release/python-31212/).
   > Version 3.12 will give you the best compatibility
2. Next - configure the Python - located under `Tools > Scripts > Python Settings` inside OBS.
   > Select the root folder the Python resides<br>
   > _Default Python folder name_: `Python311`
3. Half way there! <br>Next you need to add the script in the `Tools > Scripts`
   > Click the "+" button and select the `RecORDERvX-X.py` script.
   > 
   > For ease of use, place the script in OBS installation folder, <br>the relative path: `obs-studio\data\obs-plugins\frontend-tools\scripts`
4. Configure the script in a way you see fit
   > Explanation of the settings:
   > - __Fallback folder name__:
   >     - Folder name for recordings that couldn't be organized based on the window title.
   >     - _Default_: Any Recording
   > - __Monitored source__:
   >     - Source that is capturing the video from Game/Window
   >     - _Default_: Any Video capable source in current Scene
   > - __Organization mode__:
   >     - How should the script organize your recordings
   >     - Currently available settings:
   >        - __Basic__ - sorts media __based on Game/Window title__ and __media type__ (_Recording/Replay Buffer/Screenshot_)
   >        - __Group by Date__  - _Basic_ and also organizes media into __folders created with recording's creation date__
   >     - _Default_: Basic
   > - __Organize Replay Buffer recordings__  
   >     - Check it, if you want your screenshot files to be organized by RecORDER
   >     - _Default_: Enabled
   > - __Organize screenshots__  
   >     - Check it, if you want your Replay Buffer files to be organized by RecORDER
   >     - _Default_: Enabled
   > - __Add name of the game as a recording prefix__  
   >     - Check it, if you want your recordings to look like this:
   >        - ex. _Voices of The Void - %Filename Formatting%.mp4_
   >        - Filename Formatting is configured in `Settings > Advanced > Recording`
   >     - _Default_: Disabled



## FAQ

<details>
<summary>Work in Progress</summary>
</details>
