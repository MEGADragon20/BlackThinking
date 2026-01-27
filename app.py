from flask import Flask, json, render_template, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import uuid
import redis, os
import dotenv

dotenv.load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bvzbujcnindinicbsivvss'
socketio = SocketIO(app, cors_allowed_origins="*")

r = redis.Redis.from_url(os.environ["UPSTASH_REDIS_URL"], decode_responses=True)


# Kartenwerte und Symbole
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
RANK_VALUES = {
    'A': 11, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10
}

MAX_PLAYERS = 7

def resolve_dealer_and_finish(game):
    while game.dealer.should_draw():
        game.dealer.hand.add_card(game.deck.draw())

    game.state = 'finished'
    results = game.calculate_winnings()
    return results


class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
    
    def __repr__(self):
        return f"{self.rank}{self.suit}"
    
    def to_dict(self):
        return {'rank': self.rank, 'suit': self.suit}

class Deck:
    def __init__(self):
        self.cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]
        random.shuffle(self.cards)
    
    def draw(self):
        if not self.cards:
            self.__init__()
        return self.cards.pop()

class Hand:
    def __init__(self):
        self.cards = []
        self.bet = 0
        self.is_split = False
        self.is_doubled = False
        self.is_finished = False
    
    def add_card(self, card):
        self.cards.append(card)
    
    def get_value(self):
        value = sum(RANK_VALUES[card.rank] for card in self.cards)
        aces = sum(1 for card in self.cards if card.rank == 'A')
        
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1
        
        return value
    
    def is_blackjack(self):
        return len(self.cards) == 2 and self.get_value() == 21
    
    def is_bust(self):
        return self.get_value() > 21
    
    def can_split(self):
        return len(self.cards) == 2 and RANK_VALUES[self.cards[0].rank] == RANK_VALUES[self.cards[1].rank]
    
    def can_double(self):
        return len(self.cards) == 2 and not self.is_doubled
    
    def to_dict(self):
        return {
            'cards': [card.to_dict() for card in self.cards],
            'value': self.get_value(),
            'bet': self.bet,
            'is_blackjack': self.is_blackjack(),
            'is_bust': self.is_bust(),
            'is_finished': self.is_finished
        }

class Player:
    def __init__(self, name, player_id, balance=1000, is_bot=False):
        self.id = player_id
        self.name = name
        self.balance = balance
        self.hands = []
        self.current_hand_index = 0
        self.is_bot = is_bot
        self.is_ready = False
        self.is_active = True
    
    def add_hand(self, bet):
        hand = Hand()
        hand.bet = bet
        self.hands.append(hand)
        return hand
    
    def get_current_hand(self):
        if self.current_hand_index < len(self.hands):
            return self.hands[self.current_hand_index]
        return None
    
    def next_hand(self):
        self.current_hand_index += 1
        if self.current_hand_index >= len(self.hands):
            return None
        return self.hands[self.current_hand_index]

    
    def reset_hands(self):
        self.hands = []
        self.current_hand_index = 0
        self.is_ready = False
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'balance': self.balance,
            'hands': [hand.to_dict() for hand in self.hands],
            'current_hand_index': self.current_hand_index,
            'is_bot': self.is_bot,
            'is_ready': self.is_ready,
            'is_active': self.is_active
        }

class Dealer:
    def __init__(self):
        self.hand = Hand()
    
    def reset(self):
        self.hand = Hand()
    
    def should_draw(self):
        return self.hand.get_value() < 17
    
    def to_dict(self, hide_second_card=False):
        cards = self.hand.cards.copy()
        if hide_second_card and len(cards) > 1:
            return {
                'cards': [cards[0].to_dict(), {'rank': '?', 'suit': '🂠'}],
                'value': '?',
                'is_bust': False
            }
        return {
            'cards': [card.to_dict() for card in cards],
            'value': self.hand.get_value(),
            'is_bust': self.hand.is_bust()
        }

class Game:
    def __init__(self, room_id):
        self.room_id = room_id
        self.deck = Deck()
        self.dealer = Dealer()
        self.players = {}
        self.player_order = []
        self.current_player_index = 0
        self.state = 'waiting'  # waiting, betting, playing, dealer_turn, finished
    
    def to_redis(self):
        return json.dumps({
        'room_id': self.room_id,
        'state': self.state,
        'current_player_index': self.current_player_index,
        'player_order': self.player_order,
        'players': {pid: p.to_dict() for pid, p in self.players.items()},
        'dealer': self.dealer.to_dict(False),
        'deck': [card.to_dict() for card in self.deck.cards],
        })
    
    @classmethod
    def from_redis(cls, data):
        raw = json.loads(data)
        game = cls(raw['room_id'])
        game.state = raw['state']
        game.current_player_index = raw['current_player_index']
        game.player_order = raw['player_order']


        game.deck.cards = [Card(**c) for c in raw['deck']]
        game.dealer.hand.cards = [Card(**c) for c in raw['dealer']['cards']]

        for pid, pdata in raw['players'].items():
            player = Player(pdata['name'], pid, pdata['balance'], pdata['is_bot'])
            player.is_ready = pdata['is_ready']
            player.is_active = pdata['is_active']
            player.current_hand_index = pdata.get('current_hand_index', 0)
            for h in pdata['hands']:
                hand = Hand()
                hand.bet = h['bet']
                hand.cards = [Card(**c) for c in h['cards']]
                hand.is_finished = h['is_finished']
                player.hands.append(hand)
            game.players[pid] = player

        return game



    def add_player(self, player_id, name, balance=1000, is_bot=False):
        if len(self.players) >= MAX_PLAYERS:
            return None
        
        if player_id not in self.players:
            player = Player(name, player_id, balance, is_bot)
            self.players[player_id] = player
            self.player_order.append(player_id)
            return player
        return self.players[player_id]
    
    def remove_player(self, player_id):
        if player_id in self.players:
            del self.players[player_id]
            if player_id in self.player_order:
                self.player_order.remove(player_id)
    
    def get_current_player(self):
        if self.current_player_index < len(self.player_order):
            player_id = self.player_order[self.current_player_index]
            return self.players.get(player_id)
        return None
    
    def all_players_ready(self):
        if not self.players:
            return False
        return all(p.is_ready or not p.is_active for p in self.players.values())
    
    def start_betting(self):
        if self.all_players_ready():
            self.state = 'betting'
            for player in self.players.values():
                player.reset_hands()
            return True
        return False
    
    def all_bets_placed(self):
        return all(len(p.hands) > 0 for p in self.players.values() if p.is_active)
    
    def deal_initial_cards(self):
        if self.all_bets_placed():
            self.state = 'playing'
            self.current_player_index = 0
            
            for player_id in self.player_order:
                player = self.players[player_id]
                if player.is_active:
                    hand = player.get_current_hand()
                    if hand:
                        hand.add_card(self.deck.draw())
                        hand.add_card(self.deck.draw())

            self.dealer.hand.add_card(self.deck.draw())
            self.dealer.hand.add_card(self.deck.draw())
            return True
        return False
    
    def next_player(self):
        self.current_player_index += 1
        
        # Überspringe inaktive Spieler
        while self.current_player_index < len(self.player_order):
            player = self.get_current_player()
            if player and player.is_active:
                return player
            self.current_player_index += 1
        
        self.state = 'dealer_turn'
        return None
    
    def calculate_winnings(self):
        dealer_value = self.dealer.hand.get_value()
        dealer_bust = self.dealer.hand.is_bust()
        dealer_blackjack = self.dealer.hand.is_blackjack()
        
        results = []
        for player_id in self.player_order:
            player = self.players[player_id]
            if not player.is_active:
                continue
                
            for hand_idx, hand in enumerate(player.hands):
                hand_value = hand.get_value()
                hand_blackjack = hand.is_blackjack()
                hand_bust = hand.is_bust()
                
                if hand_bust:
                    result = 'verloren'
                    winnings = 0
                elif hand_blackjack and not dealer_blackjack:
                    result = 'blackjack'
                    winnings = hand.bet * 2.5
                    player.balance += winnings
                elif dealer_bust:
                    result = 'gewonnen'
                    winnings = hand.bet * 2
                    player.balance += winnings
                elif hand_value > dealer_value:
                    result = 'gewonnen'
                    winnings = hand.bet * 2
                    player.balance += winnings
                elif hand_value == dealer_value:
                    result = 'unentschieden'
                    winnings = hand.bet
                    player.balance += winnings
                else:
                    result = 'verloren'
                    winnings = 0
                
                results.append({
                    'player_id': player.id,
                    'player_name': player.name,
                    'hand_index': hand_idx,
                    'result': result,
                    'bet': hand.bet,
                    'winnings': winnings
                })
        
        return results
    
    def reset_round(self):
        self.deck = Deck()
        self.dealer.reset()
        for player in self.players.values():
            player.reset_hands()
        self.state = 'betting'
        self.current_player_index = 0
    
    def to_dict(self):
        current_player = self.get_current_player()
        hide_dealer_card = self.state in ['waiting', 'betting', 'playing']
        
        return {
            'room_id': self.room_id,
            'state': self.state,
            'dealer': self.dealer.to_dict(hide_dealer_card),
            'players': [self.players[pid].to_dict() for pid in self.player_order],
            'current_player_id': current_player.id if current_player else None,
            'player_count': len(self.players),
            'max_players': MAX_PLAYERS,
            'all_ready': self.all_players_ready()
        }


def get_or_create_game(room_id):
    key = f"game:{room_id}"
    data = r.get(key)
    if data:
        return Game.from_redis(data)

    game = Game(room_id)
    r.set(key, game.to_redis())
    return game


@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join_game')
def handle_join(data):
    room_id = data.get('room_id', 'default')
    player_name = data.get('name', 'Spieler')

    player_id = data.get('player_id')
    if not player_id:
        emit('error', {'message': 'player_id missing'})
        return

    game = get_or_create_game(room_id)

    # Add or load player
    player = game.add_player(player_id, player_name)
    if player is None:
        emit('error', {'message': 'Tisch ist voll! Maximal 7 Spieler erlaubt.'})
        return

    join_room(room_id)

    # Store socket -> player mapping in Redis
    r.hset(f"socket:{request.sid}", mapping={
        "room_id": room_id,
        "player_id": player_id
    })

    r.set(f"game:{room_id}", game.to_redis())

    emit('game_state', game.to_dict(), room=room_id)
    emit(
        'player_joined',
        {'player_name': player_name, 'player_count': len(game.players)},
        room=room_id
    )


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid

    user_data = r.hgetall(f"socket:{sid}")
    if not user_data:
        return

    room_id = user_data.get("room_id")
    player_id = user_data.get("player_id")

    if not room_id or not player_id:
        return

    game = get_or_create_game(room_id)

    if player_id in game.players:
        player_name = game.players[player_id].name
        game.remove_player(player_id)

        if not game.players:
            r.delete(f"game:{room_id}")
        else:
            r.set(f"game:{room_id}", game.to_redis())
            emit('game_state', game.to_dict(), room=room_id)
            emit('player_left', {'player_name': player_name}, room=room_id)

    # Cleanup socket mapping
    r.delete(f"socket:{sid}")

@socketio.on('toggle_ready')
def handle_toggle_ready(data):
    room_id = data.get('room_id')
    player_id = data.get('player_id')

    if not room_id or not player_id:
        return
    
    game = get_or_create_game(room_id)
    
    if player_id in game.players:
        player = game.players[player_id]
        player.is_ready = not player.is_ready
        
        # Wenn alle bereit sind, starte Betting-Phase
        if game.state == 'waiting' and game.all_players_ready():
            game.start_betting()
        
        r.set(f"game:{room_id}", game.to_redis())
        emit('game_state', game.to_dict(), room=room_id)

@socketio.on('place_bet')
def handle_bet(data):
    room_id = data.get('room_id')
    player_id = data.get('player_id')
    bet = data.get('bet', 10)
    
    if not room_id or not player_id:
        return
    
    game = get_or_create_game(room_id)
    
    if player_id in game.players:
        player = game.players[player_id]
        if player.balance >= bet and game.state == 'betting':
            player.balance -= bet
            player.add_hand(bet)
            
            # Wenn alle Einsätze platziert sind, starte das Spiel
            if game.all_bets_placed():
                game.deal_initial_cards()
            
            r.set(f"game:{room_id}", game.to_redis())
            emit('game_state', game.to_dict(), room=room_id)

@socketio.on('hit')
def handle_hit(data):
    room_id = data.get('room_id')
    player_id = data.get('player_id')

    if not room_id or not player_id:
        return

    game = get_or_create_game(room_id)
    current_player = game.get_current_player()

    # Not your turn
    if not current_player or current_player.id != player_id:
        return

    hand = current_player.get_current_hand()
    if not hand or hand.is_finished:
        return

    # Player draws
    hand.add_card(game.deck.draw())

    # Hand ends on bust or 21
    if hand.is_bust() or hand.get_value() == 21:
        hand.is_finished = True

        # Move to next hand / player
        if not current_player.next_hand():
            game.next_player()

    # Dealer phase
    if game.state == 'dealer_turn':
        results = resolve_dealer_and_finish(game)

        # Persist
        r.set(f"game:{room_id}", game.to_redis())

        emit('game_state', game.to_dict(), room=room_id)
        emit('round_results', {'results': results}, room=room_id)
        return

    # Persist normal state
    r.set(f"game:{room_id}", game.to_redis())
    emit('game_state', game.to_dict(), room=room_id)

@socketio.on('stand')
def handle_stand(data):
    room_id = data.get('room_id')
    player_id = data.get('player_id')

    if not room_id or not player_id:
        print("Invalid room_id or player_id")
        return

    game = get_or_create_game(room_id)
    current_player = game.get_current_player()

    # Not your turn
    if not current_player or current_player.id != player_id:
        print("Not your turn")
        return

    hand = current_player.get_current_hand()
    print(hand.cards)
    print("Is finished", hand.is_finished)
    if not hand or hand.is_finished:
        print("Invalid hand state")
        print(hand.is_finished)
        print("Player's current hand:", current_player.get_current_hand().cards)
        print("current hand index:", current_player.current_hand_index)
        return
    hand.is_finished = True

# Move to next hand / player
    if not current_player.next_hand():
        game.next_player()

    # Dealer phase
    if game.state == 'dealer_turn':
        results = resolve_dealer_and_finish(game)

        r.set(f"game:{room_id}", game.to_redis())
        emit('game_state', game.to_dict(), room=room_id)
        emit('round_results', {'results': results}, room=room_id)
        return

    # Persist normal state
    r.set(f"game:{room_id}", game.to_redis())
    emit('game_state', game.to_dict(), room=room_id)

@socketio.on('double')
def handle_double(data):
    room_id = data.get('room_id')
    player_id = data.get('player_id')

    if not room_id or not player_id:
        return

    game = get_or_create_game(room_id)
    current_player = game.get_current_player()

    # Not your turn
    if not current_player or current_player.id != player_id:
        return

    hand = current_player.get_current_hand()
    if not hand or not hand.can_double() or current_player.balance < hand.bet:
        return

    # Apply double
    current_player.balance -= hand.bet
    hand.bet *= 2
    hand.is_doubled = True

    hand.add_card(game.deck.draw())
    hand.is_finished = True

    # Advance turn
    if not current_player.next_hand():
        game.next_player()

    # Dealer phase
    if game.state == 'dealer_turn':
        results = resolve_dealer_and_finish(game)

        r.set(f"game:{room_id}", game.to_redis())
        emit('game_state', game.to_dict(), room=room_id)
        emit('round_results', {'results': results}, room=room_id)
        return

    # Persist normal state
    r.set(f"game:{room_id}", game.to_redis())
    emit('game_state', game.to_dict(), room=room_id)

@socketio.on('split')
def handle_split(data):
    room_id = data.get('room_id')
    player_id = data.get('player_id')

    if not room_id or not player_id:
        return

    game = get_or_create_game(room_id)
    current_player = game.get_current_player()

    # Not your turn or wrong phase
    if (
        game.state != 'playing'
        or not current_player
        or current_player.id != player_id
    ):
        return

    hand = current_player.get_current_hand()

    # Validate split conditions
    if (
        not hand
        or hand.is_finished
        or not hand.can_split()
        or current_player.balance < hand.bet
    ):
        return

    # Create split hand
    new_hand = Hand()
    new_hand.bet = hand.bet
    new_hand.is_split = True

    # Move one card to new hand
    new_hand.add_card(hand.cards.pop())

    # Draw one card for each hand
    hand.add_card(game.deck.draw())
    new_hand.add_card(game.deck.draw())

    # Ensure both hands are active
    hand.is_finished = False
    new_hand.is_finished = False

    # Insert new hand directly after current one
    insert_index = current_player.current_hand_index + 1
    current_player.hands.insert(insert_index, new_hand)

    # Deduct balance
    current_player.balance -= hand.bet

    # Persist and notify
    r.set(f"game:{room_id}", game.to_redis())
    emit('game_state', game.to_dict(), room=room_id)

@socketio.on('new_round')
def handle_new_round(data):
    room_id = data.get('room_id')

    if not room_id:
        return

    game = get_or_create_game(room_id)

    # Only allow reset after round finished
    if game.state != 'finished':
        return

    game.reset_round()

    r.set(f"game:{room_id}", game.to_redis())
    emit('game_state', game.to_dict(), room=room_id)


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000)