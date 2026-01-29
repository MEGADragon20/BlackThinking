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



def train_q_learning(
    net,
    episodes=500000,
    gamma=0.95,
    lr=0.05,
    epsilon_start=1.0,
    epsilon_end=0.05,
    target_update_freq=10000
):
    epsilon_decay = (epsilon_start - epsilon_end) / episodes
    epsilon = epsilon_start

    # make a copy for the strategy testing
    target_net = Network(n_in=6, n_hidden=16)
    target_net.hidden.W = net.hidden.W.copy()
    target_net.output.W = net.output.W.copy()

    for episode in range(episodes):
        transitions, _, _ = play_episode(net, epsilon)

        for state, action, reward, next_state, done in transitions:
            q_values = net.forward(state)
            target = q_values.copy()

            if done:
                target[action] = reward
            else:
                # freeze to test strats
                next_q = target_net.forward(next_state)
                target[action] = reward + gamma * np.max(next_q)

            grad = 2 * (q_values - target)
            grad = net.output.backward(grad, lr)
            net.hidden.backward(grad, lr)

        # let the main thing know the new strat
        if episode % target_update_freq == 0:
            target_net.hidden.W = net.hidden.W.copy()
            target_net.output.W = net.output.W.copy()

        epsilon = max(epsilon_end, epsilon - epsilon_decay)

        if episode % 5000 == 0:
            print(f"Episode {episode}, epsilon {epsilon:.3f}")


# Train
def evaluate(net, games=5000):
    wins = 0
    for _ in range(games):
        transitions, _, _ = play_episode(net, epsilon=0.0)
        _, _, reward, _, _ = transitions[-1]
        if reward == 1:
            wins += 1
    return wins / games