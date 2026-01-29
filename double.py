import numpy as np
import random, json
from network import Network, DECK, count, value, draw, count_highs, count_lows

def play_episode(net, epsilon=0.3):
    deck = DECK.copy()
    random.shuffle(deck)
    # remove something to simulate mid-game or late game even, leave ~ idk 20-30 cards                                                                               
    for _ in range(random.randint(0, len(DECK) - 30)):
        draw(deck)

    hand = [draw(deck), draw(deck)]
    dealer_hand = [draw(deck)]

    transitions = []

    while True:
        state = np.array([
            count(hand),
            value(dealer_hand[0]),
            len(hand),
            (count_highs(deck) - count_lows(deck))/len(deck),
            (len(DECK) - len(deck)) / len(DECK),
            int(sum(1 for card in hand if card == "A"))
        ], dtype=np.float32)

        if random.random() < epsilon:
            action = random.choice([0, 1])
        else:
            q = net.forward(state)
            action = int(q[1] > q[0])

        if action == 1:
            hand.append(draw(deck))

        done = False
        reward = 0

        if action == 0 or count(hand) >= 21:
            done = True

            while count(dealer_hand) < 17:
                dealer_hand.append(draw(deck))

            player = count(hand)
            dealer = count(dealer_hand)

            if player > 21:
                reward = -1
            elif dealer > 21 or player > dealer:
                reward = 1
            elif player < dealer:
                reward = -1
            else:
                reward = 0

        next_state = None if done else np.array([
            count(hand),
            value(dealer_hand[0]),
            len(hand),
            (count_highs(deck) - count_lows(deck))/len(deck),
            (len(DECK) - len(deck)) / len(DECK),
            int(sum(1 for card in hand if card == "A"))
        ], dtype=np.float32)

        transitions.append((state, action, reward, next_state, done))

        if done:
            break

    return transitions, hand, dealer_hand

### THIS IS JUST A COPY OF HIT.PY, THAT NEEDS TO BE ADAPTED ONLY FOR DOUBLE, WITH HIGH PUNISHMENT FOR LOSING ###