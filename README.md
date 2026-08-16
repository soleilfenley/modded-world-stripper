# Modded World Stripper
This is a script used to make modded worlds joinable after removing certain mods.

Also, I'm not good at writing README's, bite me. It's 5am... T^T
## Usage/Installing
1. Click the green button and select, Download ZIP. You can also clone the repository if you know `git`.
2. Open the directory in Terminal/Command Prompt and run: `pip install .`
3. Test the changes to your world with: `python -m modded_world_stripper.strip_mod .\world\ --no-backup`
4. You'll be asked to add the mods you want to change, please list them like:
   ```
   ars_nouveau,supplementaries,create ...
   ```
5. Once you confirm it works as expected, use: `py strip-mod.py  New World` to write your changes. (A backup will be made)
6. Enjoy your fixed world!
## Why does this exist?
The modpack I use in my [Discord Community](https://discord.gg/nwMwghhveq) had an issue where we had to remove Supplementaries to allow users compatibility with other mod versions. And for some reason, instead of fixing their mod, you're forced to use a newer version of Sodium. It's such a new version, that you can't even use other quality of life and visual mods like Shine.

It usually isn't a big deal. You can usually delete the mod and the blocks, entities, items will disappear. But Supplementaries, JUST BREAKS YOUR WORLD!! (Unless you make new playerdata? I'm not entirely sure.)
I looked at using Amulet or MCA Selector, but they don't support modded worlds to remove their blocks. So I spent my entire day making this script to fix the world... well, I did it in a morning, but it took the rest of my day to rewrite it to work with other mods and share it on GitHub~ (I'm a vtuber, I don't know how to do this coding shit :P [I do, actually])

While this script is, dead simple, I hope this script will help you save your long-term worlds! 
## What's Supported?
I've only specifically tested with Minecraft 1.21.1 worlds. I would be surprised if newer versions have a trouble with this but I can't say the same for older versions.
I've tested Supplementaries and Ars Nouveau with this mod, but I wouldn't hate if you wanted to test other mods to add to the list!
> [!IMPORTANT]
> While it's nice to see if other mods will work, I will not add a huge list of mods to the mod selector. The only mods that will be added are mods that genuinely break worlds when removed.
## How does it work?
There are many areas a mod can add data to your world saves. The system is incredibly simplistic, deleting any instance of a block in a given world. If there's a block, replace it with air. If there's an item, just remove it from existence.
Maybe someday I'll specify items or blocks to replace it, but by that point, I'd rather someone fork this and improve on it.
