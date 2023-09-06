Ce code est un script de scraping web qui extrait des données à partir de pages web en utilisant les bibliothèques requests et BeautifulSoup. Voici un résumé des fonctionnalités principales :

Le script utilise la bibliothèque requests pour effectuer des requêtes HTTP et récupérer le contenu HTML des pages web.
La bibliothèque BeautifulSoup est utilisée pour analyser le HTML et extraire des informations spécifiques.
Le script se connecte à une base de données MongoDB à l'aide de pymongo.
Il prend des URLs de départ et un nombre de documents à extraire en tant qu'arguments en ligne de commande.
Le script suit les liens sur les pages web pour atteindre d'autres pages à scraper.
Les liens à scraper sont stockés dans une collection MongoDB appelée "link" avec un statut indiquant s'ils ont été traités ou non.
Les données extraites des pages web sont stockées dans une autre collection MongoDB appelée "content".
Une troisième collection appelée "journal" est utilisée pour enregistrer les informations relatives au processus de scraping, comme les horaires de début et de fin.
Le script utilise une logique de tentatives multiples pour gérer les échecs de requêtes HTTP et les délais de traitement trop longs.
Les données extraites incluent le contenu HTML complet de la page, les balises de titre, et les balises d'emphase telles que "b", "strong", et "em".
Le script est conçu pour scraper des pages web à partir de domaines spécifiques, en limitant les liens suivis au domaine 'fr.wikipedia.org'. Cependant, il peut être adapté pour scraper d'autres domaines en modifiant la variable self.domain_limit.

Pour utiliser le script, vous devez exécuter le code en ligne de commande en fournissant les URLs de départ et le nombre de documents à extraire.
