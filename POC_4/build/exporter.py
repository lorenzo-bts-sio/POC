import time
import threading
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
from concurrent.futures import ThreadPoolExecutor
from prometheus_client import Gauge, push_to_gateway, CollectorRegistry

class MyHandler(FileSystemEventHandler):
    def __init__(self, instance):
        super().__init__()
        self.instance = instance
        self.registry = CollectorRegistry()
        self.file_event_counter = Gauge(
            'file_events',
            'File events counter',
            ['action', 'user', 'path_source', 'path_destination', 'instance', 'date', 'heure'],
            registry=self.registry
        )

    def log_event(self, action, user, path_source, destination):
        current_time = time.localtime()
        date = time.strftime("%Y-%m-%d", current_time)
        heure = time.strftime("%H:%M:%S", current_time)

        # Utiliser le compteur Prometheus pour enregistrer l'événement
        self.file_event_counter.labels(
            action=action,
            user=user,
            path_source=path_source,
            path_destination=destination,
            instance=self.instance,
            date=date,
            heure=heure
        ).inc()

        if path_source is not None and destination is not None:
            log_line = f"{date} {heure} : {user} : {action} : {path_source} : Source : {os.path.relpath(destination, '/sftp/data/')}  : Destination : {os.path.relpath(path_source, '/sftp/data/')}"
        else:
            log_line = f"{date} {heure} : {user} : {action} : {path_source}"

        print(log_line)  # Vous pouvez ajuster ceci en fonction de votre logique de journalisation

    def push_metrics_to_gateway(self):
        # Remplacez "pushgateway" par l'adresse du serveur Pushgateway
        push_gateway_url = f'http://pushgateway:9091'
        job_name = 'file_events_job'

        try:
            push_to_gateway(push_gateway_url, job=job_name, registry=self.registry, grouping_key={'instance': self.instance})
            print(f"Metrics successfully sent to Pushgateway for instance {self.instance}")
        except Exception as e:
            print(f"Failed to send metrics to Pushgateway: {e}")

    def on_created(self, event):
        action_type = "Création de dossier" if event.is_directory else "Création de fichier"
        user = self.get_file_owner(event.src_path)
        self.log_event(action_type, user, os.path.relpath(event.src_path, "/sftp/data/"), None)
        self.push_metrics_to_gateway()

    def on_modified(self, event):
        if event.is_directory:
            return
        file_creation_time = os.path.getctime(event.src_path)
        current_time = time.time()
        if current_time - file_creation_time < 3:
            return
        action = "Modification"
        user = self.get_file_owner(event.src_path)
        self.log_event(action, user, os.path.relpath(event.src_path, "/sftp/data/"), None)
        self.push_metrics_to_gateway()

    def on_deleted(self, event):
        action_type = "Suppression de dossier" if event.is_directory else "Suppression de fichier"
        # Obtenir l'utilisateur seulement si le fichier existe encore
        user = self.get_file_owner(event.src_path) if os.path.exists(event.src_path) else None
        self.log_event(action_type, user, os.path.relpath(event.src_path, "/sftp/data/"), None)
        self.push_metrics_to_gateway()

    def on_moved(self, event):
        dest_path = getattr(event, 'dest_path', None)

        if event.is_directory:
            action_type = "Déplacement de dossier"
        else:
            action_type = "Renommage" if (dest_path and os.path.exists(dest_path)) else "Déplacement de fichier"

        user = self.get_file_owner(event.src_path)
        self.log_event(action_type, user, os.path.relpath(event.src_path, "/sftp/data/"), os.path.relpath(dest_path, "/sftp/data/") if dest_path else None)
        self.push_metrics_to_gateway()

    def get_file_owner(self, path):
        # Récupérer le propriétaire du fichier
        try:
            import pwd
            stat_info = os.stat(path)
            uid = stat_info.st_uid
            user = pwd.getpwuid(uid).pw_name
        except (ImportError, KeyError):
            # En cas d'erreur lors de l'import de pwd ou si la clé n'est pas trouvée
            user = f"uid_{uid}"

        return user

def start_sshd():
    # Lancer le processus sshd en arrière-plan
    subprocess.run(['/usr/sbin/sshd', '-D', '-e'])

if __name__ == "__main__":
    # Obtenez le nom de l'hôte (hostname) de la machine en utilisant os
    instance_name = os.uname().nodename

    # Lancer le thread pour sshd
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(start_sshd)

        # Observer pour surveiller le répertoire
        path_to_watch = "/sftp/data/"
        event_handler = MyHandler(instance_name)
        observer = Observer()
        observer.schedule(event_handler, path=path_to_watch, recursive=True)
        observer.start()

        try:
            # Attendre que l'observation se termine (ou une autre condition d'arrêt)
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            # Arrêter l'observation lorsque l'utilisateur appuie sur Ctrl+C
            observer.stop()

        # Attendre que l'observation se termine complètement
        observer.join()
