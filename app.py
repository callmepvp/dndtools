from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import os, json
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app)

class Player:
    def __init__(self, name, initiative, image=None, is_player=False):
        self.name = name
        self.initiative = initiative
        self.image = image
        self.type = "player" if is_player else "npc"
        self.is_player = is_player

    def to_dict(self):
        return {
            'name': self.name,
            'initiative': self.initiative,
            'image': self.image,
            'type': self.type,
            'is_player': self.is_player
        }

class Monster(Player):
    def __init__(self, name, initiative, srd_data, image=None):
        super().__init__(name, initiative, image, False)
        self.type = "monster"
        self.srd_data = srd_data
        self.hp = srd_data.get('hit_points', 0)
        self.ac = srd_data.get('armor_class', 10)

    def to_dict(self):
        data = super().to_dict()
        data['srd_data'] = self.srd_data
        return data

# Initial players
players = [
    Player("Siim", 18, "/static/images/player1.jpg", True),
    Player("Taavi", 14, None, True),
    Player("Kaarel", 12, None, True)
]

players = sorted(players, key=lambda x: x.initiative, reverse=True)

current_index = 0
combat_turn = 1

def broadcast_turn():
    current_player = players[current_index]
    socketio.emit('update_turn', {
        'current_player': current_player.name,
        'combat_turn': combat_turn,
        'initiative_order': [p.to_dict() for p in players],
        'current_player_image': current_player.image
    })

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('next_turn')
def handle_next_turn():
    global current_index, combat_turn
    current_index += 1
    if current_index >= len(players):
        current_index = 0
        combat_turn += 1
    broadcast_turn()

@socketio.on('add_character')
def handle_add_character(data):
    global players, current_index
    name = data['name']
    initiative = int(data['initiative'])
    image = data.get('image', None)
    is_player = data.get('is_player', False)
    srd_data = data.get('srd_data', None)
    
    image_path = f"/static/images/{image}" if image else None

    if srd_data:
        new_character = Monster(name, initiative, srd_data, image_path)
    else:
        new_character = Player(name, initiative, image_path, is_player)
    
    players.append(new_character)
    # Resort initiative order
    players = sorted(players, key=lambda x: x.initiative, reverse=True)
    # Reset current_index to 0 to keep things consistent.
    current_index = 0  
    broadcast_turn()

@socketio.on('connect')
def handle_connect():
    broadcast_turn()

@app.route('/save_encounter', methods=['POST'])
def save_encounter():
    data = request.json
    monsters = []
    
    # Changed from 'initiative_order' to 'characters' to match frontend
    for char in data['characters']:
        if char.get('type') in ['monster', 'npc'] or not char.get('is_player', True):
            monster_data = {
                'name': char['name'],
                'image': char.get('image'),
                'srd_data': char.get('srd_data'),
                'is_player': False
            }
            monsters.append(monster_data)
    
    # Generate a filename with timestamp
    filename = f"encounter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_path = os.path.join('saved_encounters', filename)
    
    # Create directory if it doesn't exist
    os.makedirs('saved_encounters', exist_ok=True)
    
    with open(save_path, 'w') as f:
        json.dump(monsters, f)
    
    return {'status': 'success', 'filename': filename}

@app.route('/load_encounter', methods=['POST'])
def load_encounter():
    filename = request.json['filename']
    try:
        with open(os.path.join('saved_encounters', filename), 'r') as f:
            monsters = json.load(f)
        return {'status': 'success', 'monsters': monsters}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/list_encounters', methods=['GET'])
def list_encounters():
    try:
        files = [f for f in os.listdir('saved_encounters') if f.endswith('.json')]
        return {'status': 'success', 'files': files}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)