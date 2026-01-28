import numpy as np
import random

DECK = [str(i) for i in range(2, 10)] + ['J', 'Q', 'K', 'A']*4*4

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

def count_lows(deck):
    total = 0
    for card in deck:
        if value(card) < 7:
            total += 1
    return total

def count_highs(deck):
    total = 0
    for card in deck:
        if value(card) > 9:
            total += 1
    return total

def create_training_data() -> tuple[list[float], int]:
    deck = DECK.copy()
    random.shuffle(deck)
    hand = [draw(deck), draw(deck)]
    sum_hand = count(hand)
    dealer_card = draw(deck)
    remove_pivot = random.randint(0, len(deck)-3) # leave 3 cause maybe you'll need to draw more idk how to do this    
    drawn_deck = deck[:remove_pivot]
    delta_drawn_deck = count_highs(drawn_deck) - count_lows(drawn_deck)
    progress_deck = len(drawn_deck) / (len(DECK))
    x = [sum_hand, progress_deck, value(dealer_card), delta_drawn_deck]

    deck = deck[remove_pivot:]
    hand_final = hand + [draw(deck)]
    sum_final = count(hand_final)
    sum_dealer = count([dealer_card])
    y = 0 if sum_final > 21 or sum_final < sum_dealer else 1 # 1 meint ziehen, 0 meint nicht ziehen. 
    return x, y

def create_training_dataset() -> tuple[list[list[float]], list[int]]:
    X = []
    y = []
    for i in range(100):
        x, label = create_training_data()
        X.append(x)
        y.append(label)
    return X, y

X, y = create_training_dataset()
X = np.array(X)
Y = np.array(y)


class Layer:
    def __init__(self, n_in, n_out):
        # +1 for bias
        self.W = np.random.randn(n_out, n_in + 1) * 0.1

    @staticmethod
    def sigmoid(z):
        return 1 / (1 + np.exp(-z))

    def forward(self, x):
        # store input with bias
        self.x = np.hstack((x, [1]))
        self.z = self.W @ self.x
        self.a = self.sigmoid(self.z)
        return self.a

    def backward(self, grad, lr):
        # grad is dL/da
        dz = grad * self.a * (1 - self.a)   # dL/dz
        self.W -= lr * dz[:, None] @ self.x[None, :]
        return self.W[:, :-1].T @ dz         # dL/dx


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
                # forward
                y_hat = self.forward(x)
                total_loss += self.loss(y, y_hat)

                # backward
                grad = self.loss_grad(y, y_hat)
                grad = self.output.backward(np.array([grad]), lr)
                self.hidden.backward(grad, lr)

            if epoch % 100 == 0:
                print(f"epoch {epoch}, loss {total_loss / len(X)}")

    def predict(self, x):
        return round(self.forward(x))
net = Network(n_in=4, n_hidden=4)
net.train(X, Y, lr=0.5, epochs=10000)

for x in X:
    print(x, net.predict(x))