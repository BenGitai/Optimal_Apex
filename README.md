# Algortims Final Project: Optimal Apex

## This is the code for my Algo final project, Optimal Apex

Optimal Apex is the name of this game which has 2 main features/modes.

This code is in python as it heavily utilizes pygame and NEAT, python specific libraries.

## RacingAI.py:

The first is RacingAI.py which is the main file. In RacingAI, you can build tracks using the track editor by selecting which block you want, rotating it how you want, and then placing it. You can save these tracks and they will be stored in the tracks folder. You can then edit a track either by loading it in the track editor, or by directly going into the CSV file, which was designed to be as easy to read for a human as possible, and changing the meta data (usefull for removing elements completely).

You can then drive on these tracks by loading into a game and then entering the name of the file. You will be prompted to enter how many players you have. The current controls are stagnant with the first player being arrow keys, the second being WASD, 3rd IJKL and 4th TFGH. There is no way to switch them in game but the controls are listed in RacingAI.py at line 1248 under def drive_car and can be changed manually.

The game is based on actual physics, the cars all have weights, friction, and power values. If you want to change these values, they can be found in class Car.init on line 511. When playing the game, the car uses a set of sensors to tell both if it has crashed and what surface it is on. Due to it just being pygame, there can sometimes we glitches where the car goes into or through a wall and gets stuck. At this moment, I have mittigated the promblem but it will still occur occasionally.

There is a computer you can play against that was manually created by me. It will avoid obsticles but is not particularly fast.

## train_live_neat.py (AI)

The AI portion of the code is in the file train_live_neat.py.

In all honesty, it works sometimes, but not amazingly. The values need to be tweaked and you can figure out what should be punished and rewarded. To change reward system, values can be found in train_live_neat.py line 86 and how the punishments are carried out on line 257.

The system uses NEAT (NeuroEvolution of Augmenting Topologies), which is an evolutionary genetic algorithm. The cofiguration file is config-feedfoward.ini, you can edit it as you see fit. Currently, it has 15 inputs (LIDAR, checpoint info, car info) and 6 ouputs (foward, backwards, yes or no turn, how much to turn) but this might not be optimal.

The AI is based on simulated results which you can view. When running the program with the specified track, pygame will open a window and you will be able to watch in real time as the cars learn to drive. You can save and load neaural net files as they are being trained with S and L respectivly. These will be saved in the ai_saves folder.

In its current state, there isn't the option to race the AI as the AI has not reached a stage that it would be fun to race against but the way it is designed makes it extreamly easy to add.

# Have Fun!