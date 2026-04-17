import os
import json
import requests
import time

# --- CONFIGURACIÓN ---
BASE_URL = "https://pokeapi.co/api/v2"
DIRS = ["data/pokes", "data/moves", "data/abilities", "data/items"] 

VERSION_PRIORITY = {
    'scarlet-violet': 20, 'sword-shield': 19, 'ultra-sun-ultra-moon': 18,
    'sun-moon': 17, 'omega-ruby-alpha-sapphire': 16, 'x-y': 15,
    'black-2-white-2': 14, 'black-white': 13, 'heartgold-soulsilver': 12,
    'platinum': 11, 'diamond-pearl': 10, 'emerald': 9, 'firered-leafgreen': 8,
    'ruby-sapphire': 7, 'crystal': 6, 'gold-silver': 5, 'yellow': 4, 'red-blue': 3,
}

def setup_directories():
    for d in DIRS:
        os.makedirs(d, exist_ok=True)

def get_english_text(entries, key='flavor_text', language_key='language'):
    for entry in entries:
        if entry.get(language_key, {}).get('name') == 'en':
            return entry[key].replace('\n', ' ').replace('\f', ' ')
    return "No description available."

def get_latest_version_group(moves_data):
    highest_priority = -1
    latest_version = None
    for move in moves_data:
        for detail in move['version_group_details']:
            v_name = detail['version_group']['name']
            if v_name in VERSION_PRIORITY and VERSION_PRIORITY[v_name] > highest_priority:
                highest_priority = VERSION_PRIORITY[v_name]
                latest_version = v_name
    return latest_version

def fetch_competitive_items():
    """Obtiene objetos competitivos ignorando basura (pociones, mt, etc) y forzando megapiedras/cristales z."""
    print("\n--- Procesando Objetos Competitivos ---")
    
    item_urls = set()
    
    # 1. Obtener por atributos base (rescata bayas y objetos comunes)
    for attribute in ['holdable', 'holdable-active']:
        try:
            req = requests.get(f"{BASE_URL}/item-attribute/{attribute}").json()
            for item in req['items']:
                item_urls.add(item['url'])
        except Exception as e:
            pass

    # 2. Forzar categorías competitivas que PokeAPI olvida etiquetar bien
    competitive_categories = [
        'mega-stones', 'z-crystals', 'choice', 'held-items', 
        'species-specific', 'type-enhancement', 'bad-held-items', 
        'training', 'plates', 'jewels'
    ]
    
    for cat in competitive_categories:
        try:
            req = requests.get(f"{BASE_URL}/item-category/{cat}").json()
            for item in req['items']:
                item_urls.add(item['url'])
        except Exception as e:
            pass

    # Bolsillos (pockets) prohibidos: Elimina Pociones, Revivires, MTs, Pokeballs, etc.
    invalid_pockets = ['medicine', 'pokeballs', 'machines', 'key', 'battle', 'mail']

    for url in item_urls:
        item_name = url.split('/')[-2]
        file_path = f"data/items/{item_name}.json"
        
        if os.path.exists(file_path): 
            continue
            
        try:
            req = requests.get(url).json()
            pocket = req.get('pocket', {}).get('name', '')
            
            # FILTRO MÁGICO: Si es medicina o basura, se salta
            if pocket in invalid_pockets:
                continue
                
            effect = get_english_text(req.get('effect_entries', []), 'effect')
            if effect == "No description available.":
                effect = get_english_text(req.get('flavor_text_entries', []), 'text')
                
            item_data = {
                "id": req['id'],
                "name": req['name'],
                "effect": effect
            }
            
            with open(file_path, 'w') as f:
                json.dump(item_data, f, indent=4)
                
        except Exception as e:
            print(f"Error procesando el objeto {item_name}: {e}")

def fetch_moves_and_abilities_data(move_urls, ability_urls):
    print("\n--- Procesando Movimientos ---")
    for url in move_urls:
        move_name = url.split('/')[-2]
        file_path = f"data/moves/{move_name}.json"
        if os.path.exists(file_path): continue
        try:
            req = requests.get(url).json()
            effect = get_english_text(req.get('effect_entries', []), 'effect')
            if effect == "No description available.":
                effect = get_english_text(req.get('flavor_text_entries', []), 'flavor_text')
            move_data = {
                "name": req['name'],
                "type": req['type']['name'],
                "effect": effect,
                "base_power": req.get('power'),
                "accuracy": req.get('accuracy')
            }
            with open(file_path, 'w') as f:
                json.dump(move_data, f, indent=4)
        except Exception as e:
            pass
            
    print("\n--- Procesando Habilidades ---")
    for url in ability_urls:
        ability_name = url.split('/')[-2]
        file_path = f"data/abilities/{ability_name}.json"
        if os.path.exists(file_path): continue
        try:
            req = requests.get(url).json()
            effect = get_english_text(req.get('effect_entries', []), 'effect')
            if effect == "No description available.":
                effect = get_english_text(req.get('flavor_text_entries', []), 'flavor_text')
            ability_data = {
                "name": req['name'],
                "effect": effect,
                "pokemon_with_ability": [p['pokemon']['name'] for p in req['pokemon']]
            }
            with open(file_path, 'w') as f:
                json.dump(ability_data, f, indent=4)
        except Exception as e:
            pass

def main():
    setup_directories()
    fetch_competitive_items()
    
    print("\nObteniendo lista de especies de Pokémon...")
    species_req = requests.get(f"{BASE_URL}/pokemon-species?limit=10000").json()
    all_move_urls, all_ability_urls = set(), set()
    
    for species_item in species_req['results']:
        species_name = species_item['name']
        print(f"Procesando especie: {species_name}")
        species_data = requests.get(species_item['url']).json()
        base_moves = []
        
        for variety in species_data['varieties']:
            poke_url = variety['pokemon']['url']
            try:
                poke_data = requests.get(poke_url).json()
                poke_name = poke_data['name']
                stats = {stat['stat']['name']: stat['base_stat'] for stat in poke_data['stats']}
                bst = sum(stats.values())
                types = [t['type']['name'] for t in poke_data['types']]
                
                abilities = []
                for a in poke_data['abilities']:
                    abilities.append(a['ability']['name'])
                    all_ability_urls.add(a['ability']['url'])
                    
                sprite = poke_data['sprites']['front_default']
                moves_list = []
                
                if variety['is_default']:
                    latest_version = get_latest_version_group(poke_data['moves'])
                    for move in poke_data['moves']:
                        for detail in move['version_group_details']:
                            if detail['version_group']['name'] == latest_version:
                                moves_list.append(move['move']['name'])
                                all_move_urls.add(move['move']['url'])
                                break
                    base_moves = moves_list 
                else:
                    moves_list = base_moves
                    
                pokemon_payload = {
                    "id": poke_data['id'],
                    "name": poke_name,
                    "is_default": variety['is_default'],
                    "types": types,
                    "base_stats": stats,
                    "bst": bst,
                    "abilities": abilities,
                    "moves": moves_list,
                    "sprite": sprite
                }
                
                with open(f"data/pokes/{poke_name}.json", 'w') as f:
                    json.dump(pokemon_payload, f, indent=4)
            except Exception as e:
                pass
        time.sleep(0.1)

    fetch_moves_and_abilities_data(all_move_urls, all_ability_urls)
    print("\n¡Extracción completada con éxito!")

if __name__ == "__main__":
    main()