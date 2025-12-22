import random
import time

class LudoGameEngine:
    def __init__(self):
        # 52 Step Path (Matches your Frontend)
        self.PATH_MAP = [
            [7,2],[7,3],[7,4],[7,5],[7,6], [6,7],[5,7],[4,7],[3,7],[2,7],[1,7], 
            [1,8],[1,9], 
            [2,9],[3,9],[4,9],[5,9],[6,9], [7,10],[7,11],[7,12],[7,13],[7,14],[7,15], 
            [8,15],[9,15], 
            [9,14],[9,13],[9,12],[9,11],[9,10], [10,9],[11,9],[12,9],[13,9],[14,9],[15,9], 
            [15,8],[15,7],
            [14,7],[13,7],[12,7],[11,7],[10,7], [9,6],[9,5],[9,4],[9,3],[9,2],[9,1], 
            [8,1],[7,1] 
        ]
        self.SAFE_INDICES = [0, 8, 13, 21, 26, 34, 39, 47]
        self.START_POS = {'red': 0, 'yellow': 26}

    def create_game(self, p1_id, p2_id, bet):
        return {
            'id': f"{p1_id}_{p2_id}_{int(time.time())}",
            'players': {'red': p1_id, 'yellow': p2_id},
            'turn': 'red',
            'dice': 0,
            'waitingForMove': False,
            'red_pos': [-1, -1, -1, -1], # -1 means in base
            'yellow_pos': [-1, -1, -1, -1],
            'scores': {'red': 0, 'yellow': 0},
            'timeLeft': 300,
            'betAmount': bet,
            'prizeAmount': bet * 2 * 0.5, # 50% Rule
            'status': 'playing'
        }

    def roll_dice(self, game_state, team):
        """Securely rolls dice on server"""
        if game_state['turn'] != team or game_state['waitingForMove']:
            return None
        
        dice_val = random.randint(1, 6)
        game_state['dice'] = dice_val
        game_state['waitingForMove'] = True
        return dice_val

    def make_move(self, game_state, team, pawn_index):
        """Calculates move result"""
        if game_state['turn'] != team or not game_state['waitingForMove']:
            return None

        current_positions = game_state[f'{team}_pos']
        current_pos = current_positions[pawn_index]
        dice = game_state['dice']

        # 1. Determine New Position
        if current_pos == -1:
            new_pos = self.START_POS[team]
        else:
            new_pos = (current_pos + dice) # Logic handles cyclic path in pathMap usually

        # Update Position
        current_positions[pawn_index] = new_pos
        
        # 2. Score
        points = 1 if current_pos == -1 else dice
        game_state['scores'][team] += points

        # 3. Kill Logic
        enemy_team = 'yellow' if team == 'red' else 'red'
        enemy_positions = game_state[f'{enemy_team}_pos']
        killed = False

        if (new_pos % 52) not in self.SAFE_INDICES:
            for i, ep in enumerate(enemy_positions):
                if ep != -1 and (ep % 52) == (new_pos % 52):
                    enemy_positions[i] = -1 # Send to base
                    killed = True
        
        # Penalty
        if killed:
            game_state['scores'][enemy_team] = max(0, game_state['scores'][enemy_team] - 5)

        # 4. Next Turn
        if dice != 6 and not killed:
            game_state['turn'] = enemy_team
        
        game_state['waitingForMove'] = False
        game_state['dice'] = 0
        
        return game_state