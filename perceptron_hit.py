import numpy as np
import random

DECK = ([str(i) for i in range(2, 11)] + ['J', 'Q', 'K', 'A']) * 4

def value(string):
    if string in ["J", "Q", "K"]:
        return 10
    elif string == "A":
        return 11
    else:
        return int(string)

def draw(deck):
    card = random.choice(deck)
    deck.remove(card)
    return card

def count(hand):
    total = sum(value(card) for card in hand)
    aces = sum(1 for card in hand if card == "A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def count_lows(deck):
    return sum(1 for card in deck if value(card) < 7)

def count_highs(deck):
    return sum(1 for card in deck if value(card) > 9)
def play_episode(net, epsilon=0.3):
    deck = DECK.copy()
    random.shuffle(deck)
    # remove something to simulate mid-game or late game even, leave ~ idk 20-30 cards                                                                               
    #for _ in range(random.randint(0, len(DECK) - 30)):
    #    draw(deck)

    hand = [draw(deck), draw(deck)]
    dealer_hand = [draw(deck)]

    transitions = []

    while True:
        state = np.array([
            count(hand),
            value(dealer_hand[0]),
            len(hand),
            count_highs(deck) - count_lows(deck),
            (len(DECK) - len(deck)) / len(DECK),
            int('A' in hand)
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
            count_highs(deck) - count_lows(deck),
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

    # Initialize target network as a copy of main network
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
                # Use frozen target network for next_state
                next_q = target_net.forward(next_state)
                target[action] = reward + gamma * np.max(next_q)

            grad = 2 * (q_values - target)
            grad = net.output.backward(grad, lr)
            net.hidden.backward(grad, lr)

        # Periodically sync target network to main network
        if episode % target_update_freq == 0:
            target_net.hidden.W = net.hidden.W.copy()
            target_net.output.W = net.output.W.copy()

        epsilon = max(epsilon_end, epsilon - epsilon_decay)

        if episode % 5000 == 0:
            print(f"Episode {episode}, epsilon {epsilon:.3f}")


class Layer:
    def __init__(self, n_in, n_out):
        self.W = np.random.randn(n_out, n_in + 1) * 0.01

    @staticmethod
    def sigmoid(z):
        return 1 / (1 + np.exp(-np.clip(z, -500, 500)))

    def forward(self, x):
        self.x = np.hstack((x, [1]))
        self.z = self.W @ self.x
        self.a = self.sigmoid(self.z)
        return self.a

    def backward(self, grad, lr):
        dz = grad * self.a * (1 - self.a)
        self.W -= lr * dz[:, None] @ self.x[None, :]
        return self.W[:, :-1].T @ dz

class Network:
    def __init__(self, n_in, n_hidden):
        self.hidden = Layer(n_in, n_hidden)
        self.output = Layer(n_hidden, 2)

    def forward(self, x):
        h = self.hidden.forward(x)
        return self.output.forward(h)


    def predict(self, x):
        q = self.forward(x)
        return int(q[1] > q[0])  # 0 = stand, 1 = hit


    @staticmethod
    def loss(y, y_hat):
        return (y - y_hat) ** 2

    @staticmethod
    def loss_grad(y, y_hat):
        return 2 * (y_hat - y)

    def train(self, X, Y, lr=0.1, epochs=1000):
        for epoch in range(epochs):
            total_loss = 0
            for x, y in zip(X, Y):
                y_hat = self.forward(x)
                total_loss += self.loss(y, y_hat)
                grad = self.loss_grad(y, y_hat)
                grad = self.output.backward(np.array([grad]), lr)
                self.hidden.backward(grad, lr)

            if epoch % 100 == 0:
                print(f"epoch {epoch}, loss {total_loss / len(X):.6f}")


# Train
def evaluate(net, games=5000):
    wins = 0
    for _ in range(games):
        transitions, _, _ = play_episode(net, epsilon=0.0)
        _, _, reward, _, _ = transitions[-1]
        if reward == 1:
            wins += 1
    return wins / games
net = Network(n_in=6, n_hidden=16)  # 6 inputs now
train_q_learning(net, episodes=200000, lr=0.05)


win_rate = evaluate(net, games=5000)
print(f"\nWin rate over 5000 games: {win_rate:.2%}")
print("\nSample predictions:")
for i in range(4):
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


