import asyncio
import logging
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from openai import OpenAI

#TODO: Scraper einarbeiten in die Qdrant Vektordatenbank

#Noch nicht implementiert

# Konfiguration
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SEARCH_TERMS = ["e", "a", "kurs"]  # Einfache Suchbegriffe weil die Seite Suchbegrife benötugt
COLLECTION_NAME = "weiterbildungen"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ke übergabe
client = OpenAI(api_key=OPENAI_API_KEY)


class WeiterbildungScraper:
    def __init__(self):
        self.qdrant = QdrantClient(url=QDRANT_URL)
        self.collection = COLLECTION_NAME

    async def init_browser(self):
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(headless=True)
        logger.info("Browser initialisiert")

    async def embed_text(self, text: str):
        """Erstellt Embedding mit Fehlerbehandlung"""
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",  # Verwende das kleinere Modell
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI Fehler: {e}")
            # Fallback: Einfachen Dummy-Vektor zurückgeben
            return [0.1] * 384  # 384 Dimensionen für text-embedding-3-small

    async def scrape_search_term(self, term):
        page = await self.browser.new_page()

        try:
            logger.info(f"Scraping für Begriff: {term}")
            await page.goto("https://mein-now.de/weiterbildungssuche/", timeout=60000)
            await page.wait_for_timeout(3000)

            # Sucheingabe finden und ausfüllen
            search_input = await page.query_selector("input[type='search']")
            if search_input:
                await search_input.fill(term)
                await search_input.press("Enter")
                await page.wait_for_timeout(5000)
            else:
                logger.warning("Suchfeld nicht gefunden")
                return []

            # Mehr Ergebnisse laden
            for i in range(3):
                try:
                    load_more = await page.query_selector("#load_more_angebote")
                    if load_more and await load_more.is_visible():
                        await load_more.click()
                        await page.wait_for_timeout(3000)
                        logger.info(f"Mehr Ergebnisse geladen ({i + 1}/3)")
                    else:
                        break
                except Exception as e:
                    logger.warning(f"Konnte 'Mehr laden' nicht klicken: {e}")
                    break

            # Kurse extrahieren
            courses = await page.evaluate("""
                (searchTerm) => {
                    const items = document.querySelectorAll('article, [class*="card"], [class*="item"]');
                    console.log(`Gefundene Elemente: ${items.length}`);

                    return Array.from(items).map((item, index) => {
                        const titleElem = item.querySelector('h1, h2, h3, [class*="title"]');
                        const linkElem = item.querySelector('a');

                        return {
                            id: `course_${Date.now()}_${index}`,
                            title: titleElem ? titleElem.innerText.trim() : 'Kein Titel',
                            description: item.innerText.substring(0, 300).trim(),
                            url: linkElem ? linkElem.href : '',
                            scraped_at: new Date().toISOString(),
                            search_term: searchTerm
                        };
                    }).filter(course => course.title.length > 5); // Mindestens 5 Zeichen im Titel
                }
            """, term)

            logger.info(f"Gefunden: {len(courses)} Kurse für '{term}'")
            return courses

        except Exception as e:
            logger.error(f"Fehler beim Scraping von '{term}': {e}")
            return []
        finally:
            await page.close()

    def init_qdrant(self):
        """Initialisiert Qdrant Collection"""
        try:
            collections = self.qdrant.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection not in collection_names:
                self.qdrant.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
                logger.info(f"Collection '{self.collection}' erstellt")
            else:
                logger.info(f"Collection '{self.collection}' existiert bereits")

        except Exception as e:
            logger.error(f"Fehler bei Qdrant Initialisierung: {e}")

    async def save_courses(self, courses):
        """Speichert Kurse in Qdrant"""
        if not courses:
            logger.warning("Keine Kurse zum Speichern")
            return

        points = []
        for course in courses:
            try:
                # Embedding erstellen
                vector = await self.embed_text(course["title"] + " " + course["description"])

                points.append(
                    PointStruct(
                        id=hash(course["id"]) % (2 ** 63),
                        vector=vector,
                        payload=course
                    )
                )
            except Exception as e:
                logger.error(f"Fehler beim Verarbeiten von Kurs {course['id']}: {e}")

        if points:
            try:
                self.qdrant.upsert(
                    collection_name=self.collection,
                    points=points,
                    wait=True
                )
                logger.info(f"{len(points)} Kurse in Qdrant gespeichert")
            except Exception as e:
                logger.error(f"Fehler beim Speichern in Qdrant: {e}")

        # Zusätzlich als JSON speichern
        try:
            with open("/app/courses.json", "w", encoding="utf-8") as f:
                json.dump(courses, f, ensure_ascii=False, indent=2)
            logger.info(f"{len(courses)} Kurse in courses.json gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim JSON-Speichern: {e}")

    async def run(self):
        """Hauptfunktion"""
        try:
            await self.init_browser()
            self.init_qdrant()

            all_courses = []
            for term in SEARCH_TERMS:
                courses = await self.scrape_search_term(term)
                all_courses.extend(courses)
                await asyncio.sleep(2)  # Pause zwischen Requests

            await self.save_courses(all_courses)
            logger.info(f"SCRAPING ABGESCHLOSSEN: {len(all_courses)} Kurse gesammelt")

        except Exception as e:
            logger.error(f"Kritischer Fehler: {e}")
        finally:
            if hasattr(self, 'browser'):
                await self.browser.close()
            logger.info("Browser geschlossen")


if __name__ == "__main__":
    # Prüfe Environment Variables
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY nicht gesetzt, verwende Fallback")

    asyncio.run(WeiterbildungScraper().run())