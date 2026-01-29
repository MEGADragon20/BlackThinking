import numpy as np, random
DECK = ([str(i) for i in range(2, 11)] + ['J', 'Q', 'K', 'A']) * 16

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

    def as_dict(self):
        return {
            "hidden_W": self.hidden.W.tolist(),
            "output_W": self.output.W.tolist()
        }
    @classmethod
    def from_dict(cls, data, n_in, n_hidden):
        net = cls(n_in=n_in, n_hidden=n_hidden)
        net.hidden.W = np.array(data["hidden_W"])
        net.output.W = np.array(data["output_W"])
        return net
    
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