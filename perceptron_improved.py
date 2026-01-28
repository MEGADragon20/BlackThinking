import numpy as np
import random

DECK = [str(i) for i in range(2, 10)] + ['J', 'Q', 'K', 'A']*4*4

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
    """Calculate hand value, handling multiple Aces correctly"""
    total = sum(value(card) for card in hand)
    aces = sum(1 for card in hand if card == "A")
    
    # Reduce Aces from 11 to 1 until under 21
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    
    return total

def count_lows(deck):
    return sum(1 for card in deck if value(card) < 7)

def count_highs(deck):
    return sum(1 for card in deck if value(card) > 9)

def create_training_data() -> tuple[list[float], int]:
    """Simulate a more realistic blackjack hand"""
    deck = DECK.copy()
    random.shuffle(deck)
    
    # Initial hand
    hand = [draw(deck), draw(deck)]
    dealer_card = draw(deck)
    
    # Simulate drawing until hand is complete
    # (either bust, stand, or reach a reasonable stopping point)
    while count(hand) < 11:  # Hit on 10 or less (basic strategy)
        hand.append(draw(deck))
    
    sum_hand = count(hand)
    
    # Calculate deck composition from remaining cards
    drawn_cards = len(DECK) - len(deck)
    delta_drawn_deck = count_highs(hand + [dealer_card]) - count_lows(hand + [dealer_card])
    progress_deck = drawn_cards / len(DECK)
    
    # Features: current hand value, deck progress, dealer card, hand size, deck composition
    x = [sum_hand, progress_deck, value(dealer_card), len(hand), delta_drawn_deck]
    
    # Determine if standing was good decision
    # Check if dealer would bust or if hand beats dealer
    dealer_hand = [dealer_card]
    while count(dealer_hand) < 17:
        dealer_hand.append(draw(deck))
    
    sum_dealer = count(dealer_hand)
    
    # 1 = good decision (hand wins or dealer busts), 0 = bad decision
    y = 1 if sum_hand <= 21 and (sum_dealer > 21 or sum_hand > sum_dealer) else 0
    
    return x, y

def create_training_dataset(size=500) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for _ in range(size):
        x, label = create_training_data()
        X.append(x)
        y.append(label)
    return np.array(X), np.array(y)

X, Y = create_training_dataset(500)  # Increased dataset size
X_original = X.copy()
# Normalize features
X_mean, X_std = X.mean(axis=0), X.std(axis=0) + 1e-8
X = (X - X_mean) / X_std

class Layer:
    def __init__(self, n_in, n_out):
        self.W = np.random.randn(n_out, n_in + 1) * 0.01

    @staticmethod
    def sigmoid(z):
        return 1 / (1 + np.exp(-np.clip(z, -500, 500)))  # Clip to prevent overflow

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
        self.output = Layer(n_hidden, 1)

    def forward(self, x):
        h = self.hidden.forward(x)
        y_hat = self.output.forward(h)
        return y_hat[0]

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

            if epoch % 500 == 0:
                print(f"epoch {epoch}, loss {total_loss / len(X):.6f}")

    def predict(self, x):
        return round(self.forward(x))

net = Network(n_in=5, n_hidden=8)  # 5 inputs now
net.train(X, Y, lr=0.5, epochs=5000)

print("\nSample predictions:")
for i, x in enumerate(X[:100]):
    print(f"Input: {x}, Prediction: {net.predict(x)}, Actual: {Y[i]}")
print("sum_hand, progress_deck, value(dealer_card), len(hand), delta_drawn_deck")
print(X_original[:100])