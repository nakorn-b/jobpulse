import requests

class RemoteOKScraper:
    def __init__(self):
        self.url = "https://remoteok.com/api"

    def scrape_jobs(self):
        response = requests.get(self.url)
        jobs = response.json()

        return jobs