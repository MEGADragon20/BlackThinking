# BlackThinking

BlackJack app with Flask, that contains a well-trained bot.

## Description

The project consists of two parts currently: An interface to play classic BlackJack and a training environment for a neuronal network that learns whether to hit or to stand. The first part is made with Flask SocketIO, allowing a smooth gameplay for groups up to 7 players (6 + 1 bot). Additionally, the main.py provides methods to simplyfy hitting, standing, (doubeling and splitting) for the bots. The bots are part of the class defined in network.py, currently trained in hit_training.py. When a satisfying result is reached, the weight-matrix is stored in a json to simplify access during the game and avoid long waiting-times when deploying

## Getting Started

### Dependencies

* Runs on Windows, Linux, MacOS, probably on every OS supporting python
* python3 + pip
* python package dependencies in [requirements.txt](https://github.com/MEGADragon20/BlackThinking/blob/main/requirements.txt)

### Installing

* clone the repo
* you need to create an .env file containing this key: ´´´UPSTASH_REDIS_URL´´´ (it should point to your redis. Start.py hosts redis locally so if you run it (after installing docker) you can simply set ´´´UPSTASH_REDIS_URL=redis://localhost:6379´´´ but check the remaining instructions first)

### Executing program

* create a venv running ```python3 -m venv .venv```
* On Linux/MacOS run:
```
source .venv/bin/activate
```
* On Windows run
```
\.venv\Scripts\activate
```
* to install python packages run:
```
pip install -r requirements.txt
```
* Now you have two options:
    * run the app using local redis running ```python3 start.py```
    * run the app with other redis running ```python3 app.py```
## Help

Start an issue on github I will answer swiftly.

## Acknowledgments

Template for README.md
* [Here](https://gist.githubusercontent.com/DomPizzie/7a5ff55ffa9081f2de27c315f5018afc/raw/d59043abbb123089ad6602aba571121b71d91d7f/README-Template.md)