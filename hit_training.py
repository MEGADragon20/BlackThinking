import numpy as np
import random, json
from hit_prod import Network, train_q_learning, evaluate, count, value, draw, count_highs, count_lows, DECK, play_episode

net = Network(n_in=6, n_hidden=32)
train_q_learning(net, episodes=500000, lr=0.05)


win_rate = evaluate(net, games=5000)
print(f"\nWin rate over 5000 games: {win_rate:.2%}")
print("\nSample predictions:")
for i in range(20):
    transitions, player_hand, dealer_hand = play_episode(net, epsilon=0.0)
    actions = [t[1] for t in transitions]
    last_action = actions[-1]
    if last_action == 0:
        num_hits = sum(actions[:-1])
    else:
        num_hits = sum(actions)
    
    current_hand = player_hand[:2]
    print(f"Initial Hand: {', '.join(current_hand)} ({count(current_hand)})")
    for i in range(num_hits):
        drawn_card = player_hand[2 + i]
        current_hand.append(drawn_card)
        print(f" -> Hit -> {', '.join(current_hand)} ({count(current_hand)})")
    if last_action == 0:
        print(f" -> Stand -> {', '.join(current_hand)} ({count(current_hand)})")
    print(f" | {dealer_hand[0]}, {count(dealer_hand)}")         



if win_rate >= 0.41:
    a = input("keep y/n")
    if a == "y":
        with open("hit.json", "w") as f:
            json.dump(net.as_dict(), f, indent=4)