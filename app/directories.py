DIRECTORIES = [
    {
        "key": "apple_podcasts",
        "name": "Apple Podcasts",
        "submit_url": "https://podcastsconnect.apple.com/",
        "note": "Submit your RSS feed once. Apple re-crawls it automatically after that — several other "
                "directories (Pocket Casts, Overcast, Podcast Addict, Player FM) pull their listing from "
                "Apple's directory, so this is the single most important one to get right.",
    },
    {
        "key": "spotify",
        "name": "Spotify",
        "submit_url": "https://podcasters.spotify.com/",
        "note": "Submit your RSS feed once via Spotify for Podcasters. New episodes are picked up "
                "automatically after that.",
    },
    {
        "key": "amazon_music",
        "name": "Amazon Music / Audible",
        "submit_url": "https://podcasters.amazon.com/",
        "note": "Submit your RSS feed once via Amazon Music for Podcasters.",
    },
    {
        "key": "pandora",
        "name": "Pandora",
        "submit_url": "https://podcasters.amazon.com/",
        "note": "Pandora podcasts run on the same Amazon Music for Podcasters system — submitting there "
                "covers both.",
    },
    {
        "key": "iheartradio",
        "name": "iHeartRadio",
        "submit_url": "https://www.iheart.com/",
        "note": "No public self-serve submission form. Usually indexed automatically from Apple Podcasts' "
                "directory within a few days; contact iHeart support if your show doesn't appear.",
    },
    {
        "key": "pocket_casts",
        "name": "Pocket Casts",
        "submit_url": "https://pocketcasts.com/",
        "note": "No submission needed — Pocket Casts indexes shows automatically from your public RSS "
                "feed and from Apple's directory.",
    },
    {
        "key": "overcast",
        "name": "Overcast",
        "submit_url": "https://overcast.fm/",
        "note": "No submission needed — listeners can add your feed directly by URL, and Overcast also "
                "indexes from Apple's directory.",
    },
    {
        "key": "podcast_addict",
        "name": "Podcast Addict",
        "submit_url": "https://podcastaddict.com/",
        "note": "No submission needed — indexes automatically from your RSS feed and Apple's directory.",
    },
    {
        "key": "castbox",
        "name": "Castbox",
        "submit_url": "https://castbox.fm/",
        "note": "Usually auto-indexed from your RSS feed; Castbox also offers a creator portal to claim "
                "your show for extra features.",
    },
    {
        "key": "player_fm",
        "name": "Player FM",
        "submit_url": "https://player.fm/",
        "note": "No submission needed — indexes automatically from your RSS feed.",
    },
    {
        "key": "podchaser",
        "name": "Podchaser",
        "submit_url": "https://www.podchaser.com/",
        "note": "Indexes automatically, but you can claim your show as its creator for a verified profile.",
    },
    {
        "key": "tunein",
        "name": "TuneIn",
        "submit_url": "https://tunein.com/",
        "note": "Requires a manual application and editorial review through TuneIn's partner process — "
                "look for their podcast submission form.",
    },
]

DIRECTORIES_BY_KEY = {d["key"]: d for d in DIRECTORIES}
