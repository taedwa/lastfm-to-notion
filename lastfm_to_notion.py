import requests
import json

# Replace these with your actual keys and IDs
LASTFM_API_KEY = 'your_lastfm_api_key'
LASTFM_USER = 'your_lastfm_username'
NOTION_TOKEN = 'your_notion_integration_token'
NOTION_DATABASE_ID_ALBUMS = 'your_notion_database_id_for_albums'

# Headers for the Notion API
notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def get_top_albums(user, api_key, limit=100):
    """Fetch all top albums for a user by handling pagination."""
    albums = []
    page = 1
    total_pages = 1  # Initialize with 1 to enter the loop

    while page <= total_pages:
        url = (
            f"http://ws.audioscrobbler.com/2.0/?method=user.gettopalbums"
            f"&user={user}&api_key={api_key}&format=json&limit={limit}&page={page}"
        )
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error fetching page {page}: {response.status_code}, {response.text}")
            break

        data = response.json()

        # Extract albums from the current page
        current_page_albums = data.get('topalbums', {}).get('album', [])
        albums.extend(current_page_albums)

        # Determine total pages from the response
        attr = data.get('topalbums', {}).get('@attr', {})
        total_pages = int(attr.get('totalPages', 1))
        print(f"Fetched page {page} of {total_pages}")
        page += 1

    return albums

def get_existing_albums_from_notion(notion_headers, database_id):
    """Retrieve existing albums from the Notion database."""
    existing_albums = set()
    has_more = True
    start_cursor = None

    while has_more:
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        data = {
            "page_size": 100,
            "start_cursor": start_cursor
        } if start_cursor else {"page_size": 100}

        response = requests.post(url, headers=notion_headers, data=json.dumps(data))
        if response.status_code != 200:
            print(f"Error fetching existing albums: {response.status_code}, {response.text}")
            break

        results = response.json()
        for result in results.get("results", []):
            properties = result.get("properties", {})
            album_name = properties.get("Album Name", {}).get("title", [{}])[0].get("text", {}).get("content", "")
            artist_name = properties.get("Artist Name", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
            existing_albums.add((album_name, artist_name))

        has_more = results.get("has_more", False)
        start_cursor = results.get("next_cursor", None)

    return existing_albums

def create_notion_page_for_album(album, notion_headers, database_id, existing_albums):
    """Create a Notion page for a single album if it meets the play count criteria
    and is not already in the database.
    """
    try:
        plays = int(album['playcount'])
    except (KeyError, ValueError):
        print(f"Invalid playcount for album: {album}")
        return

    album_name = album.get('name', 'Unknown Album')
    artist_name = album.get('artist', {}).get('name', 'Unknown Artist')

    # Skip albums that already exist in Notion
    if (album_name, artist_name) in existing_albums:
        print(f"Skipping already existing album: {album_name} by {artist_name}")
        return

    if plays > 100:  # Only add albums with more than 100 plays
        # Get the largest available album cover image
        images = album.get('image', [])
        album_cover_url = images[-1]['#text'] if images else ''

        # JSON payload to create a new page in Notion
        data = {
            "parent": { "database_id": database_id },
            "properties": {
                "Album Name": {
                    "title": [
                        {
                            "text": {
                                "content": album_name
                            }
                        }
                    ]
                },
                "Artist Name": {
                    "rich_text": [
                        {
                            "text": {
                                "content": artist_name
                            }
                        }
                    ]
                },
                "Play Count": {
                    "number": plays
                },
                "Album Cover": {
                    "files": [
                        {
                            "name": f"{album_name} Cover",
                            "type": "external",
                            "external": {
                                "url": album_cover_url
                            }
                        }
                    ]
                }
            }
        }

        response = requests.post("https://api.notion.com/v1/pages", headers=notion_headers, data=json.dumps(data))
        if response.status_code != 200:
            print(f"Failed to create page for {album_name}: {response.status_code}, {response.text}")
        else:
            print(f"Successfully created page for {album_name}")

def main():
    # Step 1: Get existing albums from Notion
    existing_albums = get_existing_albums_from_notion(notion_headers, NOTION_DATABASE_ID_ALBUMS)

    # Step 2: Fetch top albums from Last.fm
    albums = get_top_albums(LASTFM_USER, LASTFM_API_KEY, limit=100)
    print(f"Total albums fetched: {len(albums)}")

    # Step 3: Add new albums to Notion if they don't already exist
    for album in albums:
        create_notion_page_for_album(album, notion_headers, NOTION_DATABASE_ID_ALBUMS, existing_albums)

if __name__ == "__main__":
    main()
