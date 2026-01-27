import numpy as np
import random

DECK = [str(i) for i in range(2, 10)] + ['J', 'Q', 'K', 'A']

def value(string):
    if string == "J" or string == "Q" or string == "K":
        return 10
    elif string == "A":
        return 11
    else:
        return int(string)

def draw(deck):
    card = random.choice(deck)
    deck.remove(card)
    return card


def delta(deck):
    delta = []
    for card in DECK:
        if card not in deck:
            delta.append(card)
    return delta

def count(hand):
    total = 0
    for i in hand:
        total += value(i)
        if total > 21 and i == "A":
            total -= 10
    return total

def create_training_data() -> tuple[list[float], int]:
    deck = DECK.copy()
    random.shuffle(deck)
    hand = [draw(deck), draw(deck)]
    sum_hand = count(hand)
    dealer_card = draw(deck)
    remove_pivot = random.randint(0, len(deck)-3) # leave 3 cause maybe you'll need to draw more idk how to do this    
    drawn_deck = deck[:remove_pivot]
    sum_drawn_deck = 0
    for i in drawn_deck:
        sum_drawn_deck += value(i)
    progress_deck = len(drawn_deck) / (len(DECK))
    x = [sum_hand, progress_deck, value(dealer_card), sum_drawn_deck]

    deck = deck[remove_pivot:]
    hand_final = hand + [draw(deck)]
    sum_final = count(hand_final)
    y = 0 if sum_final > 21 else 1 # 1 meint ziehen, 0 meint nicht ziehen. 
    return x, y

def create_training_dataset() -> tuple[list[list[float]], list[int]]:
    X = []
    y = []
    for i in range(20):
        x, label = create_training_data()
        X.append(x)
        y.append(label)
    return X, y

print(create_training_dataset())

X = [
    [0, 0],
    [1, 0],
    [0, 1],
    [1, 1]
]
y = [0, 0, 0, 1]  


class Perceptron:
    def __init__(self, n, learning_rate=0.01):
        self.weights = [1 for _ in range(n+1)]
        self.learning_rate = learning_rate

    def activate(self, x):
        return 1 if x > 0 else 0

    def predict(self, x):
        weighted_sum = np.dot(np.hstack(([1], x)), self.weights)
        return self.activate(weighted_sum)

    def train(self, X, y, epochs=100):
        for _ in range(epochs):
            for i in range(len(X)):
                self.train_once(X[i], y[i])

    def train_once(self, x, y):
        prediction = self.predict(x)
        error = y - prediction
        self.weights += self.learning_rate * error * np.hstack(([1], x))

a = Perceptron(2)
a.train(X, y)
print(a.weights)