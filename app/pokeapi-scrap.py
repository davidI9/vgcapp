import os
import json
import requests

# Configuración de URLs
API_BASE = "https://pokeapi.co/api/v2"

# Jerarquía de versiones para determinar el "último juego principal" (Excluyendo Arceus)
VERSION_PRIORITY = [
    'scarlet-violet',
    'sword-shield',
    'brilliant-diamond-shining-pearl',
    'ultra-sun-ultra-moon',
    'sun-moon',
    'omega-ruby-alpha-sapphire',
    'x-y',
    'black-2-white-2',
    'black-white',
    'heartgold-soulsilver',
    'platinum',
    'diamond-pearl',
    'firered-leafgreen',
    'emerald',
    'ruby-sapphire',
    'crystal',
    'gold-silver',
    'yellow',
    'red-blue'
]

def create_directories():
    """Crea los directorios necesarios si no existen."""
    dirs = ['data/pokes', 'data/moves', 'data/abilities']
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def get_english_text(entries, key='effect'):
    """Busca y devuelve el texto en inglés de una lista de entradas."""
    for entry in entries:
        if entry.get('language', {}).get('name') == 'en':
            return entry.get(key, entry.get('flavor_text', '')).replace('\n', ' ').replace('\f', ' ')
    return "No description available."

def get_latest_version_group(moves_data):
    """Encuentra el grupo de versiones más reciente en el que el Pokémon aprendió movimientos."""
    available_versions = set()
    for move in moves_data:
        for details in move.get('version_group_details', []):
            available_versions.add(details['version_group']['name'])
            
    for version in VERSION_PRIORITY:
        if version in available_versions:
            return version
    return None

def fetch_json(url):
    """Realiza la petición GET y devuelve el JSON."""
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def process_pokemon_data():
    create_directories()
    
    print("Obteniendo la lista de todas las especies de Pokémon...")
    species_list_data = fetch_json(f"{API_BASE}/pokemon-species?limit=2000")
    if not species_list_data:
        print("Error al conectar con PokeAPI.")
        return

    species_results = species_list_data['results']
    
    # Sets para recolectar las URLs de movimientos y habilidades sin duplicados
    moves_to_fetch = {}
    abilities_to_fetch = {}

    # Para pruebas, puedes limitar el slice, ej: species_results[:10]
    for species_info in species_results:
        species_name = species_info['name']
        print(f"Procesando especie: {species_name}")
        
        species_data = fetch_json(species_info['url'])
        if not species_data:
            continue
            
        varieties = species_data.get('varieties', [])
        
        # 1. Identificar la forma base (default)
        base_variety = next((v for v in varieties if v['is_default']), None)
        if not base_variety:
            continue
            
        base_pokemon_data = fetch_json(base_variety['pokemon']['url'])
        if not base_pokemon_data:
            continue

        # 2. Determinar la versión más reciente y filtrar movimientos de la forma base
        moves_data = base_pokemon_data.get('moves', [])
        latest_version = get_latest_version_group(moves_data)
        
        base_moves_list = []
        if latest_version:
            for move in moves_data:
                for details in move['version_group_details']:
                    if details['version_group']['name'] == latest_version:
                        move_name = move['move']['name']
                        base_moves_list.append(move_name)
                        moves_to_fetch[move_name] = move['move']['url']
                        break # Ya validamos que lo aprende en esta versión

        # 3. Iterar sobre TODAS las formas (incluyendo la base)
        for variety in varieties:
            form_name = variety['pokemon']['name']
            
            # Usar los datos base ya descargados o descargar los de la forma alternativa
            if variety['is_default']:
                form_data = base_pokemon_data
            else:
                form_data = fetch_json(variety['pokemon']['url'])
                if not form_data:
                    continue
            
            # Extraer Estadísticas y calcular el BST
            stats = {}
            bst = 0
            for stat in form_data.get('stats', []):
                stat_name = stat['stat']['name']
                base_stat = stat['base_stat']
                stats[stat_name] = base_stat
                bst += base_stat
                
            # Extraer Tipos
            types = [t['type']['name'] for t in form_data.get('types', [])]
            
            # Extraer Habilidades y guardarlas para luego
            abilities = []
            for ab in form_data.get('abilities', []):
                ab_name = ab['ability']['name']
                abilities.append(ab_name)
                abilities_to_fetch[ab_name] = ab['ability']['url']
                
            # Extraer Sprite 2D (oficial artwork o front_default)
            sprites = form_data.get('sprites', {})
            sprite_url = sprites.get('other', {}).get('official-artwork', {}).get('front_default')
            if not sprite_url:
                sprite_url = sprites.get('front_default')

            # Estructurar el JSON del Pokémon
            poke_json = {
                "id": form_data['id'],
                "name": form_name,
                "species": species_name,
                "latest_game_version": latest_version,
                "types": types,
                "base_stats": stats,
                "bst": bst,
                "abilities": abilities,
                "moves": base_moves_list, # Heredan de la forma base en la última gen
                "sprite_url": sprite_url
            }
            
            # Guardar en data/pokes
            with open(f"data/pokes/{form_name}.json", "w", encoding="utf-8") as f:
                json.dump(poke_json, f, indent=4)
                
    # 4. Descargar y procesar todos los Movimientos únicos encontrados
    print(f"\nDescargando {len(moves_to_fetch)} movimientos...")
    for move_name, move_url in moves_to_fetch.items():
        move_data = fetch_json(move_url)
        if not move_data:
            continue
            
        effect_desc = get_english_text(move_data.get('effect_entries', []), 'effect')
        if effect_desc == "No description available.":
            # Algunos movimientos solo tienen flavor_text
            effect_desc = get_english_text(move_data.get('flavor_text_entries', []), 'flavor_text')

        move_json = {
            "name": move_name,
            "type": move_data.get('type', {}).get('name'),
            "power": move_data.get('power'),
            "accuracy": move_data.get('accuracy'),
            "effect_description": effect_desc
        }
        
        with open(f"data/moves/{move_name}.json", "w", encoding="utf-8") as f:
            json.dump(move_json, f, indent=4)

    # 5. Descargar y procesar todas las Habilidades únicas encontradas
    print(f"\nDescargando {len(abilities_to_fetch)} habilidades...")
    for ab_name, ab_url in abilities_to_fetch.items():
        ab_data = fetch_json(ab_url)
        if not ab_data:
            continue
            
        effect_desc = get_english_text(ab_data.get('effect_entries', []), 'effect')
        if effect_desc == "No description available.":
            effect_desc = get_english_text(ab_data.get('flavor_text_entries', []), 'flavor_text')
            
        pokemon_with_ability = [p['pokemon']['name'] for p in ab_data.get('pokemon', [])]

        ab_json = {
            "name": ab_name,
            "effect_description": effect_desc,
            "pokemon": pokemon_with_ability
        }
        
        with open(f"data/abilities/{ab_name}.json", "w", encoding="utf-8") as f:
            json.dump(ab_json, f, indent=4)
            
    print("\n¡Proceso completado! Todos los datos han sido almacenados en el directorio 'data/'.")

if __name__ == "__main__":
    # Advertencia: Esto realizará varios miles de peticiones a PokeAPI.
    # El proceso completo puede tardar varios minutos.
    process_pokemon_data()