from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bvzbujcnindinicbsivvss'
socketio = SocketIO(app, cors_allowed_origins="*")

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
        return self.get_current_hand()
    
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
                    if hand.is_blackjack():
                        print("Blackjack!")
                    #    hand.is_finished = True
                    #    next_player = self.next_player()
                    #    if next_player is None:
                    #        self.state = 'dealer_turn'

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

# Globale Spiele-Verwaltung
games = {}

def get_or_create_game(room_id):
    if room_id not in games:
        games[room_id] = Game(room_id)
    return games[room_id]

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join_game')
def handle_join(data):
    room_id = data.get('room_id', 'default')
    player_name = data.get('name', 'Spieler')
    
    if 'player_id' not in session:
        session['player_id'] = str(uuid.uuid4())
    
    player_id = session['player_id']
    session['room_id'] = room_id
    
    game = get_or_create_game(room_id)
    
    # Spieler hinzufügen oder bestehenden Spieler laden
    player = game.add_player(player_id, player_name)
    
    if player is None:
        emit('error', {'message': 'Tisch ist voll! Maximal 7 Spieler erlaubt.'})
        return
    
    join_room(room_id)
    
    emit('game_state', game.to_dict(), room=room_id)
    emit('player_joined', {'player_name': player_name, 'player_count': len(game.players)}, room=room_id)

@socketio.on('disconnect')
def handle_disconnect():
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    
    if room_id and player_id and room_id in games:
        game = games[room_id]
        if player_id in game.players:
            player_name = game.players[player_id].name
            game.remove_player(player_id)
            
            # Wenn keine Spieler mehr da sind, lösche das Spiel
            if not game.players:
                del games[room_id]
            else:
                emit('game_state', game.to_dict(), room=room_id)
                emit('player_left', {'player_name': player_name}, room=room_id)

@socketio.on('toggle_ready')
def handle_toggle_ready():
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    
    if not room_id or not player_id:
        return
    
    game = get_or_create_game(room_id)
    
    if player_id in game.players:
        player = game.players[player_id]
        player.is_ready = not player.is_ready
        
        # Wenn alle bereit sind, starte Betting-Phase
        if game.state == 'waiting' and game.all_players_ready():
            game.start_betting()
        
        emit('game_state', game.to_dict(), room=room_id)

@socketio.on('place_bet')
def handle_bet(data):
    room_id = session.get('room_id')
    player_id = session.get('player_id')
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
            
            emit('game_state', game.to_dict(), room=room_id)

@socketio.on('hit')
def handle_hit():
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    
    if not room_id or not player_id:
        return
    
    game = get_or_create_game(room_id)
    current_player = game.get_current_player()
    
    if current_player and current_player.id == player_id:
        hand = current_player.get_current_hand()
        if hand and not hand.is_finished:
            hand.add_card(game.deck.draw())
            
            if hand.is_bust() or hand.get_value() == 21:
                hand.is_finished = True
                next_hand = current_player.next_hand()
                if not next_hand:
                    next_player = game.next_player()
                    if next_player is None:
                        game.state = 'dealer_turn'

            emit('game_state', game.to_dict(), room=room_id)

    if hand.is_bust() or hand.get_value() == 21:
        hand.is_finished = True
        next_hand = current_player.next_hand()
        if not next_hand:
            game.next_player()
            if next_player is None:
                        game.state = 'dealer_turn'

    if game.state == 'dealer_turn':
        results = resolve_dealer_and_finish(game)
        emit('game_state', game.to_dict(), room=room_id)
        emit('round_results', {'results': results}, room=room_id)
    else:
        emit('game_state', game.to_dict(), room=room_id)

@socketio.on('stand')
def handle_stand():
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    
    if not room_id or not player_id:
        return
    
    game = get_or_create_game(room_id)
    current_player = game.get_current_player()
    
    if current_player and current_player.id == player_id:
        hand = current_player.get_current_hand()
        if hand:
            hand.is_finished = True
        
        next_hand = current_player.next_hand()
        if not next_hand:
            game.next_player()
        
        # Dealer spielt
        if game.state == 'dealer_turn':
            while game.dealer.should_draw():
                game.dealer.hand.add_card(game.deck.draw())
            
            game.state = 'finished'
            results = game.calculate_winnings()
            
            emit('game_state', game.to_dict(), room=room_id)
            emit('round_results', {'results': results}, room=room_id)
        else:
            emit('game_state', game.to_dict(), room=room_id)

@socketio.on('double')
def handle_double():
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    
    if not room_id or not player_id:
        return
    
    game = get_or_create_game(room_id)
    current_player = game.get_current_player()
    
    if current_player and current_player.id == player_id:
        hand = current_player.get_current_hand()
        if hand and hand.can_double() and current_player.balance >= hand.bet:
            current_player.balance -= hand.bet
            hand.bet *= 2
            hand.is_doubled = True
            hand.add_card(game.deck.draw())
            hand.is_finished = True
            
            next_hand = current_player.next_hand()
            if not next_hand:
                game.next_player()
            
            if game.state == 'dealer_turn':
                while game.dealer.should_draw():
                    game.dealer.hand.add_card(game.deck.draw())
                
                game.state = 'finished'
                results = game.calculate_winnings()
                
                emit('game_state', game.to_dict(), room=room_id)
                emit('round_results', {'results': results}, room=room_id)
            else:
                emit('game_state', game.to_dict(), room=room_id)

@socketio.on('split')
def handle_split():
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    
    if not room_id or not player_id:
        return
    
    game = get_or_create_game(room_id)
    current_player = game.get_current_player()
    
    if current_player and current_player.id == player_id:
        hand = current_player.get_current_hand()
        if hand and hand.can_split() and current_player.balance >= hand.bet:
            new_hand = Hand()
            new_hand.bet = hand.bet
            new_hand.is_split = True
            new_hand.add_card(hand.cards.pop())
            
            hand.add_card(game.deck.draw())
            new_hand.add_card(game.deck.draw())
            
            current_player.hands.insert(current_player.current_hand_index + 1, new_hand)
            current_player.balance -= hand.bet
            
            emit('game_state', game.to_dict(), room=room_id)

@socketio.on('new_round')
def handle_new_round():
    room_id = session.get('room_id')
    
    if not room_id:
        return
    
    game = get_or_create_game(room_id)
    game.reset_round()
    
    emit('game_state', game.to_dict(), room=room_id)

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000)