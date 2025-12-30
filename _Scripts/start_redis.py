#!/usr/bin/env python3
"""
Script pour démarrer Redis pour Ollama Manager
Ce script vérifie si Redis est en cours d'exécution et le démarre si nécessaire
"""

import subprocess
import sys
import time
import socket


def is_redis_running(host="localhost", port=6379):
    """Vérifie si Redis est en cours d'exécution"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result == 0
    except Exception:
        return False


def start_redis():
    """Démarre Redis en utilisant la commande appropriée"""
    commands = [
        ["redis-server"],
        ["redis-server", "--daemonize", "yes"],
        ["brew", "services", "start", "redis"],
    ]
    
    for cmd in commands:
        try:
            print(f"Tentative de démarrage Redis avec: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            # Si la commande a réussi (code de sortie 0) ou si Redis est déjà configuré
            if result.returncode == 0 or "already running" in result.stderr.lower():
                print("Redis démarré avec succès!")
                return True
        except subprocess.TimeoutExpired:
            print(f"La commande {' '.join(cmd)} a expiré, mais Redis peut être en cours de démarrage...")
            return True
        except FileNotFoundError:
            # La commande n'existe pas, essayer la prochaine
            continue
        except Exception as e:
            print(f"Erreur lors du démarrage de Redis: {e}")
            continue
    
    return False


def main():
    """Fonction principale"""
    print("Vérification du statut de Redis...")
    
    if is_redis_running():
        print("✅ Redis est déjà en cours d'exécution sur localhost:6379")
        sys.exit(0)
    
    print("❌ Redis n'est pas en cours d'exécution. Tentative de démarrage...")
    
    if start_redis():
        # Attendre un peu que Redis démarre
        print("Attente du démarrage de Redis...")
        time.sleep(2)
        
        if is_redis_running():
            print("✅ Redis est maintenant en cours d'exécution!")
            print("\nVous pouvez maintenant lancer l'application Ollama Manager avec:")
            print("FLASK_APP=wsgi.py flask run")
            print("\nEt dans un autre terminal, lancez le worker RQ:")
            print("rq worker ollama")
        else:
            print("⚠️ Redis a été démarré mais n'est pas encore accessible. Veuillez réessayer dans quelques instants.")
    else:
        print("❌ Impossible de démarrer Redis automatiquement.")
        print("\nVeuillez démarrer Redis manuellement:")
        print("1. Si vous avez installé Redis via Homebrew: brew services start redis")
        print("2. Sinon: redis-server --daemonize yes")
        print("3. Ou simplement: redis-server")
        print("\nSi Redis n'est pas installé, installez-le avec:")
        print("brew install redis  (sur macOS)")
        print("ou suivez les instructions sur https://redis.io/download")
        sys.exit(1)


if __name__ == "__main__":
    main()