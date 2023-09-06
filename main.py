import requests
from bs4 import BeautifulSoup
import pymongo
from urllib.parse import urljoin, urldefrag, urlparse
import datetime
import argparse
import time
import pickle


class Scraper:
    """
    Retourne une base de données et un ensemble de collections dans MongoDB

        Attributes:
            start_urls (str): une liste de chaines de charactères comprenant un ou plusieurs urls
            nb_doc (int): nombre de documents pour la collection content (par url)
        Methods:
            scrape_website:
                Lance le scraping sur une page web donnée
            _scrape_link:
                Lance le scraping sur les urls générés par la page web donnée
            retry_request:
                Permet de tester si un scraping dure trop longtemps
            _get_url_links:
                Récupère les liens contenu sur une page web donnée
            _insert_content:
                Insert dans la collection content dans MongoDB le contenu d'une page web
            _insert_journal:
                Insert dans la collection journal dans MongoDB les évènements lors du processus
            _insert_links:
                Insert dans la collection link dans MongoDB l'ensemble des liens récupérer à partir d'une page web donnée'

    """
    def __init__(self, start_urls, nb_doc):
        """
        Initialise l'ensemble des attributs nécessaires pour le web scraping

            Parameters:
                start_urls (str): un ou plusieurs urls
                nb_doc (int): nombre de docuements récupérés dans la collection content

        """
        self.domain_limit = 'fr.wikipedia.org'
        self.start_urls = start_urls
        self.visited_urls = set()
        self.db_client = pymongo.MongoClient('mongodb://localhost:27017/')
        self.db = self.db_client['scraping_db']
        self.link_collection = self.db['link']
        self.metadata_collection = self.db['content']
        self.journal_collection = self.db['journal']
        self.count = 0
        self.nb_doc = nb_doc
        # Nombre maximum de tentatives
        self.max_attempts = 10
        # Temps d'attente en secondes entre chaque tentative
        self.retry_interval = 60

    def scrape_website(self):
        """
        Lance une session de web scraping

        """
        for start_url in self.start_urls:
            self.count += self.nb_doc
            start_time = datetime.datetime.now()
            self.journal_collection.insert_one({'id_session': start_url + str(start_time),'url': start_url, 'start_session': start_time})
            self.journal_collection.find_one_and_update({'url': start_url}, {"$set": {'id_session': start_url + str(start_time), 'start_session': start_time}})
            self._scrape_link(start_url, start_url)
            # tant qu'il reste des liens en attentes et < 10 documents
            while self.metadata_collection.count_documents({}) < self.count and self.link_collection.find({'status': 'to do'}):
                # récupère le lien à scraper
                doc = self.link_collection.find_one({"status": 'to do'})
                link = doc['url']

                # modifie le status en "en-cours"
                self.link_collection.find_one_and_update({'url': link}, {"$set": {'status': 'in process'}})
                self.start_time = datetime.datetime.now()
                # web scraping de la page donnée
                self._scrape_link(link, start_url)

                end_time = datetime.datetime.now()

                # modifie le status en "fini"
                self.link_collection.find_one_and_update({'url': link}, {"$set": {'status': 'done'}})
                self.journal_collection.find_one_and_update({'url': link}, {"$set": {'start': start_time, 'end': end_time}})

            self.journal_collection.find_one_and_update({'id_session': start_url + str(start_time)}, {"$set": {'end_session': datetime.datetime.now()}})
            print('Web scraping done.')

    def _scrape_link(self, url, start_url):
        """
        Lance le web scraping sur des urls et insert directement dans la base de données les collections

            Parameter:
                url (str): une chaine de charactère qui correspond à une url

        """
        try:
            print("get_url", url)
            response = self.retry_request(url)
            cookies = response.cookies

            if response is not None:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Récupère les liens d'une page web
                new_links = self._get_url_links(url, soup)
                # Enlève les doublons
                unique_new_links = sorted(set(new_links))

                # Collection 1: link
                self._insert_links(unique_new_links, pickle.dumps(cookies))

                # Collection 2: metadata
                self._insert_metadata(url, soup)

                # Collection 3: journal
                if url != start_url:
                    self._insert_journal(url)

        except requests.exceptions.RequestException as e:
            print(f'Erreur lors de la requête pour la page {url}: {e}')

    def retry_request(self, url, max_retries=10, retry_interval=60):
        """
        Test pour savoir si un lien met trop de temps à être scrapé

            Parameters:
                url (str): une chaine de charactère qui correspond à une url
                max_retries (int): nombre de tentatives
                retry_interval (int): intervalle avant de re-tester

            Return:
                response (reponse): la réponse du serveur suite à une requête HTTP

        """
        for i in range(max_retries):
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    return response
                else:
                    print(f'La requête pour la page {url} a échoué avec le code de statut : {response.status_code}')
                    document = {
                        'url': url,
                        'error': response.status_code,
                        'date': datetime.datetime.now()
                    }
                    self.journal_collection.insert_one(document)
            except requests.exceptions.RequestException as e:
                print(f'Erreur lors de la requête pour la page {url}: {e}')
                document = {
                    'url': url,
                    'error': e,
                    'date': datetime.datetime.now()
                }
                self.journal_collection.insert_one(document)

            print(f"Réessayer la requête {i + 1} fois")
            time.sleep(retry_interval)

            elapsed_time = datetime.datetime.now() - self.start_time
            if int(elapsed_time.total_seconds()) > 60:  # Test si cela fait 1 min
                print(f"Le traitement du lien {url} prend trop de temps. Relance de la requête.")
                continue

        return None

    def _get_url_links(self, url, soup):
        """
        Récupère les liens issus d'une page web

            Parameters:
                url (str): une chaine de charactère qui correspond à une url
                soup (BeautifulSoup): un objet BeautifulSoup qui représente le document web

            Return:
                links (list): liste des liens récupérés
        """
        link_tags = soup.find_all('a')
        links = []
        for tag in link_tags:
            if 'href' in tag.attrs:
                link_url = urljoin(url, tag['href'])
                # Enlève le fragment
                link_url = urldefrag(link_url)[0]
                # Parse un url en 6 parties
                parsed_url = urlparse(link_url)
                # Test si le domaine de l'url reste bien dans le domaine délimité
                if parsed_url.netloc == self.domain_limit:
                    links.append(link_url)
        return links

    def _insert_links(self, unique_links, cookies):
        """
        Insert des documents dans la collection link

                Parameter:
                    unique_links (list): les liens issus d'une page web sans doublons

        """
        for link in unique_links:
            try:
                self.link_collection.insert_one({
                    "url": link,
                    'status': 'to do',
                    'cookies': cookies
                })
            except pymongo.errors.DuplicateKeyError:
                pass

    def _insert_metadata(self, url, soup):
        """
        Insert les données contenu d'une page web dans la collection content

            Parameters:
                url (str): une chaine de charactère qui correspond à une url
                soup (BeautifulSoup): un objet BeautifulSoup qui représente le document web

        """
        try:
            # Insertion des données de la page
            # Extraire les balises de titre de la page
            title_tags = soup.find_all(['title', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

            # Récupérer le contenu des balises de titre
            title_content = [tag.get_text().strip() for tag in title_tags]

            # Extraire les balises d'emphase de la page
            emphasis_tags = soup.find_all(['b', 'strong', 'em'])

            # Récupérer le contenu des balises d'emphase
            emphasis_content = [tag.get_text().strip() for tag in emphasis_tags]

            document = {
                'url': url,
                'html': str(soup),
                'titles': title_content,
                'emphasis': emphasis_content
            }
            self.metadata_collection.insert_one(document)
        except pymongo.errors.DuplicateKeyError:
            pass


    def _insert_journal(self, url):
        """
        Insert les évènements dans la collection journal

            Parameter:
                url (str): une chaine de charactère qui correspond à une url

        """
        try:
            document = {
                'url': url,
            }
            self.journal_collection.insert_one(document)
        except pymongo.errors.DuplicateKeyError:
            pass


# exemple d'urls à tester = ['https://fr.wikipedia.org/wiki/France', 'https://fr.wikipedia.org/wiki/Pomme']

parser = argparse.ArgumentParser(description='Scraper')
parser.add_argument('url', type=str, nargs = '+', help='Starting URL for web scraping')
parser.add_argument('count', type=int, help='Number of doc')

args = parser.parse_args()

scraper = Scraper(args.url, args.count)
scraper.scrape_website()