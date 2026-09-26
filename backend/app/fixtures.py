"""Built-in sample data so a tree can be drawn with no network access.

The Yardbirds family, with dates approximated from public band histories.
Records are produced in the same normalised shape the MusicBrainz client
emits, so the demo exercises exactly the same pipeline as a live search.
"""

PEOPLE = {
    "keith-relf": ("Keith Relf", "1976-05-14"), "chris-dreja": ("Chris Dreja", None),
    "paul-samwell-smith": ("Paul Samwell-Smith", None), "jim-mccarty": ("Jim McCarty", None),
    "top-topham": ("Top Topham", None), "eric-clapton": ("Eric Clapton", None),
    "jeff-beck": ("Jeff Beck", "2023-01-10"), "jimmy-page": ("Jimmy Page", None),
    "jack-bruce": ("Jack Bruce", "2014-10-25"), "ginger-baker": ("Ginger Baker", "2019-10-06"),
    "steve-winwood": ("Steve Winwood", None), "ric-grech": ("Ric Grech", "1990-03-17"),
    "bobby-whitlock": ("Bobby Whitlock", None), "carl-radle": ("Carl Radle", "1980-05-30"),
    "jim-gordon": ("Jim Gordon", "2023-03-13"), "john-mayall": ("John Mayall", None),
    "john-mcvie": ("John McVie", None), "bernie-watson": ("Bernie Watson", None),
    "roger-dean": ("Roger Dean", None), "martin-hart": ("Martin Hart", None),
    "hughie-flint": ("Hughie Flint", None), "peter-green": ("Peter Green", "2020-07-25"),
    "aynsley-dunbar": ("Aynsley Dunbar", None), "mick-fleetwood": ("Mick Fleetwood", None),
    "keef-hartley": ("Keef Hartley", None), "mick-taylor": ("Mick Taylor", None),
    "tony-reeves": ("Tony Reeves", None), "steve-thompson": ("Steve Thompson", None),
    "colin-allen": ("Colin Allen", None), "rod-stewart": ("Rod Stewart", None),
    "ronnie-wood": ("Ronnie Wood", None), "micky-waller": ("Micky Waller", None),
    "tony-newman": ("Tony Newman", None), "nicky-hopkins": ("Nicky Hopkins", "1994-09-06"),
    "robert-plant": ("Robert Plant", None), "john-paul-jones": ("John Paul Jones", None),
    "john-bonham": ("John Bonham", "1980-09-25"), "jane-relf": ("Jane Relf", None),
    "john-hawken": ("John Hawken", None), "louis-cennamo": ("Louis Cennamo", None),
    "annie-haslam": ("Annie Haslam", None), "michael-dunford": ("Michael Dunford", None),
    "john-tout": ("John Tout", None), "jon-camp": ("Jon Camp", None),
    "terry-sullivan": ("Terry Sullivan", None), "martin-pugh": ("Martin Pugh", None),
    "bobby-caldwell": ("Bobby Caldwell", None), "ronnie-lane": ("Ronnie Lane", "1997-06-04"),
    "kenney-jones": ("Kenney Jones", None), "ian-mclagan": ("Ian McLagan", "2014-12-03"),
    "tetsu-yamauchi": ("Tetsu Yamauchi", None), "steve-marriott": ("Steve Marriott", "1991-04-20"),
    "jimmy-winston": ("Jimmy Winston", None), "peter-frampton": ("Peter Frampton", None),
    "greg-ridley": ("Greg Ridley", None), "jerry-shirley": ("Jerry Shirley", None),
    "clem-clempson": ("Clem Clempson", None), "jeremy-spencer": ("Jeremy Spencer", None),
    "bob-brunning": ("Bob Brunning", None), "danny-kirwan": ("Danny Kirwan", "2018-06-08"),
    "christine-mcvie": ("Christine McVie", "2022-11-30"), "bob-welch": ("Bob Welch", "2012-06-07"),
    "bob-weston": ("Bob Weston", None), "dave-walker": ("Dave Walker", None),
    "lindsey-buckingham": ("Lindsey Buckingham", None), "stevie-nicks": ("Stevie Nicks", None),
}

V, G, B, D, K = "lead vocals", "guitar", "bass guitar", "drums (drum set)", "keyboard"

BANDS = {
    "yardbirds": ("The Yardbirds", "1963-05", "1968-07", [
        ("keith-relf", "1963-05", "1968-07", [V, "harmonica"]),
        ("chris-dreja", "1963-05", "1966-06", ["rhythm guitar"]),
        ("chris-dreja", "1966-06", "1968-07", [B]),
        ("paul-samwell-smith", "1963-05", "1966-06", [B]),
        ("jim-mccarty", "1963-05", "1968-07", [D]),
        ("top-topham", "1963-05", "1963-10", ["lead guitar"]),
        ("eric-clapton", "1963-10", "1965-03", ["lead guitar"]),
        ("jeff-beck", "1965-03", "1966-11", ["lead guitar"]),
        ("jimmy-page", "1966-06", "1968-07", ["lead guitar"]),
    ]),
    "bluesbreakers": ("John Mayall's Bluesbreakers", "1963-01", "1969-06", [
        ("john-mayall", "1963-01", "1969-06", [V, K, "harmonica"]),
        ("john-mcvie", "1963-01", "1967-05", [B]),
        ("bernie-watson", "1963-01", "1964-04", [G]),
        ("martin-hart", "1963-01", "1964-01", [D]),
        ("hughie-flint", "1964-01", "1966-06", [D]),
        ("roger-dean", "1964-04", "1965-04", [G]),
        ("eric-clapton", "1965-04", "1966-07", [G]),
        ("jack-bruce", "1965-11", "1965-12", [B]),
        ("aynsley-dunbar", "1966-06", "1967-02", [D]),
        ("peter-green", "1966-07", "1967-06", [G]),
        ("mick-fleetwood", "1967-02", "1967-05", [D]),
        ("keef-hartley", "1967-05", "1968-06", [D]),
        ("tony-reeves", "1967-05", "1968-06", [B]),
        ("mick-taylor", "1967-06", "1969-06", [G]),
        ("steve-thompson", "1968-06", "1969-06", [B]),
        ("colin-allen", "1968-06", "1969-06", [D]),
    ]),
    "cream": ("Cream", "1966-07", "1968-11", [
        ("eric-clapton", "1966-07", "1968-11", [G, V]),
        ("jack-bruce", "1966-07", "1968-11", [B, V]),
        ("ginger-baker", "1966-07", "1968-11", [D]),
    ]),
    "blind-faith": ("Blind Faith", "1969-02", "1969-10", [
        ("eric-clapton", "1969-02", "1969-10", [G]),
        ("steve-winwood", "1969-02", "1969-10", [V, K]),
        ("ginger-baker", "1969-02", "1969-10", [D]),
        ("ric-grech", "1969-05", "1969-10", [B, "violin"]),
    ]),
    "dominos": ("Derek and the Dominos", "1970-05", "1971-05", [
        ("eric-clapton", "1970-05", "1971-05", [G, V]),
        ("bobby-whitlock", "1970-05", "1971-05", [K, V]),
        ("carl-radle", "1970-05", "1971-05", [B]),
        ("jim-gordon", "1970-05", "1971-05", [D]),
    ]),
    "jeff-beck-group": ("The Jeff Beck Group", "1967-02", "1969-07", [
        ("jeff-beck", "1967-02", "1969-07", [G]),
        ("rod-stewart", "1967-02", "1969-07", [V]),
        ("ronnie-wood", "1967-02", "1969-07", [B]),
        ("aynsley-dunbar", "1967-02", "1967-12", [D]),
        ("micky-waller", "1968-01", "1969-02", [D]),
        ("nicky-hopkins", "1968-06", "1969-07", ["piano"]),
        ("tony-newman", "1969-02", "1969-07", [D]),
    ]),
    "led-zeppelin": ("Led Zeppelin", "1968-09", "1980-12", [
        ("jimmy-page", "1968-09", "1980-12", [G]),
        ("robert-plant", "1968-09", "1980-12", [V]),
        ("john-paul-jones", "1968-09", "1980-12", [B, K]),
        ("john-bonham", "1968-09", "1980-09", [D]),
    ]),
    "renaissance": ("Renaissance", "1969-01", "1980-06", [
        ("keith-relf", "1969-01", "1970-05", [V, G]),
        ("jim-mccarty", "1969-01", "1970-05", [D, V]),
        ("jane-relf", "1969-01", "1970-05", [V]),
        ("john-hawken", "1969-01", "1970-05", ["piano"]),
        ("louis-cennamo", "1969-01", "1970-05", [B]),
        ("annie-haslam", "1971-01", "1980-06", [V]),
        ("michael-dunford", "1971-01", "1980-06", [G]),
        ("john-tout", "1971-01", "1980-06", [K]),
        ("jon-camp", "1972-01", "1980-06", [B]),
        ("terry-sullivan", "1971-01", "1980-06", [D]),
    ]),
    "armageddon": ("Armageddon", "1974-06", "1976-05", [
        ("keith-relf", "1974-06", "1976-05", [V]),
        ("martin-pugh", "1974-06", "1976-05", [G]),
        ("louis-cennamo", "1974-06", "1976-05", [B]),
        ("bobby-caldwell", "1974-06", "1976-05", [D]),
    ]),
    "faces": ("Faces", "1969-06", "1975-12", [
        ("rod-stewart", "1969-06", "1975-12", [V]),
        ("ronnie-wood", "1969-06", "1975-12", [G]),
        ("ronnie-lane", "1969-06", "1973-06", [B, V]),
        ("kenney-jones", "1969-06", "1975-12", [D]),
        ("ian-mclagan", "1969-06", "1975-12", [K]),
        ("tetsu-yamauchi", "1973-07", "1975-12", [B]),
    ]),
    "small-faces": ("Small Faces", "1965-06", "1969-03", [
        ("steve-marriott", "1965-06", "1969-03", [V, G]),
        ("ronnie-lane", "1965-06", "1969-03", [B]),
        ("kenney-jones", "1965-06", "1969-03", [D]),
        ("jimmy-winston", "1965-06", "1965-11", [K]),
        ("ian-mclagan", "1965-11", "1969-03", [K]),
    ]),
    "humble-pie": ("Humble Pie", "1969-04", "1975-03", [
        ("steve-marriott", "1969-04", "1975-03", [V, G]),
        ("peter-frampton", "1969-04", "1971-10", [G, V]),
        ("greg-ridley", "1969-04", "1975-03", [B]),
        ("jerry-shirley", "1969-04", "1975-03", [D]),
        ("clem-clempson", "1971-10", "1975-03", [G]),
    ]),
    "fleetwood-mac": ("Fleetwood Mac", "1967-07", None, [
        ("peter-green", "1967-07", "1970-05", [G, V]),
        ("mick-fleetwood", "1967-07", None, [D]),
        ("jeremy-spencer", "1967-07", "1971-02", [G, V]),
        ("bob-brunning", "1967-07", "1967-09", [B]),
        ("john-mcvie", "1967-09", None, [B]),
        ("danny-kirwan", "1968-08", "1972-08", [G, V]),
        ("christine-mcvie", "1970-08", "1998-12", [K, V]),
        ("bob-welch", "1971-04", "1974-12", [G, V]),
        ("dave-walker", "1972-09", "1973-06", [V]),
        ("bob-weston", "1972-09", "1973-10", [G]),
        ("lindsey-buckingham", "1975-01", "1987-08", [G, V]),
        ("stevie-nicks", "1975-01", "1991-12", [V]),
        ("lindsey-buckingham", "1997-03", "2018-04", [G, V]),
        ("stevie-nicks", "1997-03", None, [V]),
        ("christine-mcvie", "2014-01", "2022-11", [K, V]),
    ]),
}

# --- AC/DC family ---
PEOPLE.update({
    "angus-young": ("Angus Young", None), "malcolm-young": ("Malcolm Young", "2017-11-18"),
    "dave-evans": ("Dave Evans", None), "larry-van-kriedt": ("Larry Van Kriedt", None),
    "colin-burgess": ("Colin Burgess", None), "rob-bailey": ("Rob Bailey", None),
    "peter-clack": ("Peter Clack", None), "bon-scott": ("Bon Scott", "1980-02-19"),
    "mark-evans": ("Mark Evans", None), "phil-rudd": ("Phil Rudd", None),
    "cliff-williams": ("Cliff Williams", None), "brian-johnson": ("Brian Johnson", None),
    "simon-wright": ("Simon Wright", None), "chris-slade": ("Chris Slade", None),
    "stevie-young": ("Stevie Young", None), "axl-rose": ("Axl Rose", None),
    "george-young": ("George Young", "2017-10-22"), "harry-vanda": ("Harry Vanda", None),
    "stevie-wright": ("Stevie Wright", "2015-12-26"), "dick-diamonde": ("Dick Diamonde", None),
    "snowy-fleet": ("Snowy Fleet", None), "tony-cahill": ("Tony Cahill", None),
    "vince-lovegrove": ("Vince Lovegrove", "2012-03-24"), "wyn-milson": ("Wyn Milson", None),
    "bruce-howe": ("Bruce Howe", None), "mick-jurd": ("Mick Jurd", None),
    "john-bisset": ("John Bisset", None), "john-freeman": ("John Freeman", None),
    "uncle-john-ayers": ("Uncle John Ayers", None), "vic-malcolm": ("Vic Malcolm", None),
    "tom-hill": ("Tom Hill", None), "brian-gibson": ("Brian Gibson", None),
    "angry-anderson": ("Angry Anderson", None), "geordie-leach": ("Geordie Leach", None),
    "paul-grant": ("Paul Grant", None), "pete-wells": ("Pete Wells", "2006-03-27"),
    "mick-cocks": ("Mick Cocks", "2009-12-22"), "dallas-royall": ("Dallas Royall", "1991-10-01"),
    "mick-stubbs": ("Mick Stubbs", None), "laurie-wisefield": ("Laurie Wisefield", None),
    "mick-cook": ("Mick Cook", None), "jim-diamond": ("Jim Diamond", "2015-10-08"),
    "danny-mcintosh": ("Danny McIntosh", None), "graham-broad": ("Graham Broad", None),
    "jim-keays": ("Jim Keays", "2014-06-13"), "doug-ford": ("Doug Ford", None),
    "glenn-wheatley": ("Glenn Wheatley", "2022-02-01"), "manfred-mann": ("Manfred Mann", None),
    "mick-rogers": ("Mick Rogers", None), "colin-pattenden": ("Colin Pattenden", None),
    "chris-thompson": ("Chris Thompson", None), "dave-flett": ("Dave Flett", None),
    "paul-rodgers": ("Paul Rodgers", None), "tony-franklin": ("Tony Franklin", None),
    "slash": ("Slash", None), "izzy-stradlin": ("Izzy Stradlin", None),
    "duff-mckagan": ("Duff McKagan", None), "steven-adler": ("Steven Adler", None),
    "matt-sorum": ("Matt Sorum", None), "dizzy-reed": ("Dizzy Reed", None),
    "gilby-clarke": ("Gilby Clarke", None), "tommy-stinson": ("Tommy Stinson", None),
    "richard-fortus": ("Richard Fortus", None), "frank-ferrer": ("Frank Ferrer", None),
    "melissa-reese": ("Melissa Reese", None),
})

BANDS.update({
    "acdc": ("AC/DC", "1973-11", None, [
        ("malcolm-young", "1973-11", "2014-09", [G]),
        ("angus-young", "1973-11", None, ["lead guitar"]),
        ("dave-evans", "1973-11", "1974-09", [V]),
        ("larry-van-kriedt", "1973-11", "1974-02", [B]),
        ("colin-burgess", "1973-11", "1974-02", [D]),
        ("rob-bailey", "1974-03", "1974-12", [B]),
        ("peter-clack", "1974-03", "1975-01", [D]),
        ("bon-scott", "1974-10", "1980-02", [V]),
        ("phil-rudd", "1975-01", "1983-08", [D]),
        ("mark-evans", "1975-03", "1977-06", [B]),
        ("cliff-williams", "1977-06", "2016-09", [B]),
        ("brian-johnson", "1980-04", "2016-03", [V]),
        ("simon-wright", "1983-08", "1989-11", [D]),
        ("chris-slade", "1989-11", "1994-08", [D]),
        ("phil-rudd", "1994-08", "2014-11", [D]),
        ("stevie-young", "2014-09", "2016-09", [G]),
        ("chris-slade", "2015-02", "2016-09", [D]),
        ("axl-rose", "2016-04", "2016-09", [V]),
        ("brian-johnson", "2018-08", None, [V]),
        ("stevie-young", "2018-08", None, [G]),
        ("cliff-williams", "2018-08", None, [B]),
        ("phil-rudd", "2018-08", None, [D]),
    ]),
    "marcus-hook-roll-band": ("Marcus Hook Roll Band", "1972-09", "1974-06", [
        ("harry-vanda", "1972-09", "1974-06", [G]),
        ("george-young", "1972-09", "1974-06", [B, V]),
        ("malcolm-young", "1972-09", "1973-10", [G]),
        ("angus-young", "1972-09", "1973-10", [G]),
    ]),
    "easybeats": ("The Easybeats", "1964-06", "1969-10", [
        ("stevie-wright", "1964-06", "1969-10", [V]),
        ("harry-vanda", "1964-06", "1969-10", [G]),
        ("george-young", "1964-06", "1969-10", ["rhythm guitar"]),
        ("dick-diamonde", "1964-06", "1969-10", [B]),
        ("snowy-fleet", "1964-06", "1967-01", [D]),
        ("tony-cahill", "1967-01", "1969-10", [D]),
    ]),
    "flash-and-the-pan": ("Flash and the Pan", "1976-06", "1992-12", [
        ("harry-vanda", "1976-06", "1992-12", [G, K]),
        ("george-young", "1976-06", "1992-12", [V, K]),
    ]),
    "valentines": ("The Valentines", "1966-01", "1970-08", [
        ("bon-scott", "1966-01", "1970-08", [V]),
        ("vince-lovegrove", "1966-01", "1970-08", [V]),
        ("wyn-milson", "1966-01", "1970-08", [G]),
    ]),
    "fraternity": ("Fraternity", "1970-01", "1974-06", [
        ("bon-scott", "1970-01", "1973-12", [V]),
        ("bruce-howe", "1970-01", "1974-06", [B]),
        ("mick-jurd", "1970-01", "1972-12", [G]),
        ("john-bisset", "1970-01", "1972-12", [K]),
        ("uncle-john-ayers", "1970-06", "1973-12", ["harmonica"]),
        ("john-freeman", "1971-01", "1974-06", [D]),
    ]),
    "geordie": ("Geordie", "1971-06", "1978-06", [
        ("brian-johnson", "1971-06", "1978-06", [V]),
        ("vic-malcolm", "1971-06", "1975-06", [G]),
        ("tom-hill", "1971-06", "1978-06", [B]),
        ("brian-gibson", "1971-06", "1978-06", [D]),
    ]),
    "buster-brown": ("Buster Brown", "1973-06", "1975-06", [
        ("angry-anderson", "1973-06", "1975-06", [V]),
        ("geordie-leach", "1973-06", "1975-06", [B]),
        ("paul-grant", "1973-06", "1975-06", [G]),
        ("phil-rudd", "1973-06", "1974-12", [D]),
    ]),
    "rose-tattoo": ("Rose Tattoo", "1976-01", "1987-06", [
        ("angry-anderson", "1976-01", "1987-06", [V]),
        ("pete-wells", "1976-01", "1983-06", ["slide guitar"]),
        ("mick-cocks", "1976-06", "1983-06", [G]),
        ("geordie-leach", "1976-06", "1983-06", [B]),
        ("dallas-royall", "1976-06", "1983-06", [D]),
    ]),
    "home": ("Home", "1970-06", "1974-06", [
        ("mick-stubbs", "1970-06", "1974-06", [V]),
        ("laurie-wisefield", "1970-06", "1974-06", [G]),
        ("cliff-williams", "1970-06", "1974-06", [B]),
        ("mick-cook", "1970-06", "1974-06", [D]),
    ]),
    "bandit": ("Bandit", "1975-06", "1977-06", [
        ("jim-diamond", "1975-06", "1977-06", [V]),
        ("danny-mcintosh", "1975-06", "1977-06", [G]),
        ("cliff-williams", "1975-06", "1977-06", [B]),
        ("graham-broad", "1975-06", "1977-06", [D]),
    ]),
    "masters-apprentices": ("The Masters Apprentices", "1968-06", "1972-06", [
        ("jim-keays", "1968-06", "1972-06", [V]),
        ("doug-ford", "1968-06", "1972-06", [G]),
        ("glenn-wheatley", "1968-06", "1972-01", [B]),
        ("colin-burgess", "1968-09", "1972-06", [D]),
    ]),
    "manfreds-earth-band": ("Manfred Mann's Earth Band", "1971-06", "1987-12", [
        ("manfred-mann", "1971-06", "1987-12", [K]),
        ("mick-rogers", "1971-06", "1975-12", [G, V]),
        ("colin-pattenden", "1971-06", "1977-06", [B]),
        ("chris-slade", "1971-06", "1978-06", [D]),
        ("chris-thompson", "1975-12", "1987-12", [V]),
        ("dave-flett", "1975-12", "1977-06", [G]),
    ]),
    "the-firm": ("The Firm", "1984-01", "1986-12", [
        ("jimmy-page", "1984-01", "1986-12", [G]),
        ("paul-rodgers", "1984-01", "1986-12", [V]),
        ("tony-franklin", "1984-01", "1986-12", [B]),
        ("chris-slade", "1984-01", "1986-12", [D]),
    ]),
    "guns-n-roses": ("Guns N' Roses", "1985-06", None, [
        ("axl-rose", "1985-06", None, [V]),
        ("slash", "1985-06", "1996-10", ["lead guitar"]),
        ("izzy-stradlin", "1985-06", "1991-11", ["rhythm guitar"]),
        ("duff-mckagan", "1985-06", "1997-08", [B]),
        ("steven-adler", "1985-06", "1990-07", [D]),
        ("matt-sorum", "1990-07", "1997-04", [D]),
        ("dizzy-reed", "1990-01", None, [K]),
        ("gilby-clarke", "1991-11", "1994-06", ["rhythm guitar"]),
        ("tommy-stinson", "1998-01", "2016-01", [B]),
        ("richard-fortus", "2002-01", None, ["rhythm guitar"]),
        ("frank-ferrer", "2006-06", None, [D]),
        ("slash", "2016-01", None, ["lead guitar"]),
        ("duff-mckagan", "2016-01", None, [B]),
        ("melissa-reese", "2016-06", None, [K]),
    ]),
})

GENRES = {"yardbirds": ["blues rock", "rhythm and blues"], "acdc": ["hard rock", "heavy metal"]}
ROOT_KEYS = {"yardbirds", "acdc"}

SAMPLES = {
    "yardbirds": {
        "id": "demo:yardbirds",
        "name": "The Yardbirds (demo)",
        "description": "Offline sample: The Yardbirds and the bands they spawned. Dates are approximate.",
        "default_depth": 3,
    },
    "acdc": {
        "id": "demo:acdc",
        "name": "AC/DC (demo)",
        "description": "Offline sample: AC/DC, the bands they came from and went on to. Dates are approximate.",
        "default_depth": 3,
    },
}


def _pid(key):
    return f"demo:person:{key}"


def _bid(key):
    return f"demo:{key}" if key in ROOT_KEYS else f"demo:band:{key}"


def build_records():
    records = {}
    for key, (name, died) in PEOPLE.items():
        records[_pid(key)] = {
            "mbid": _pid(key), "name": name, "type": "Person", "disambiguation": "",
            "begin": None, "end": died, "ended": died is not None, "memberships": [],
        }
    for key, (name, begin, end, members) in BANDS.items():
        band = {
            "mbid": _bid(key), "name": name, "type": "Group", "disambiguation": "",
            "begin": begin, "end": end, "ended": end is not None, "memberships": [],
            "genres": GENRES.get(key, []),
        }
        for person, m_begin, m_end, attrs in members:
            m = {
                "person_id": _pid(person), "person_name": PEOPLE[person][0],
                "band_id": band["mbid"], "band_name": name,
                "begin": m_begin, "end": m_end, "ended": m_end is not None, "attributes": attrs,
            }
            band["memberships"].append(m)
            records[_pid(person)]["memberships"].append(dict(m))
        records[band["mbid"]] = band
    return records


class OfflineClient:
    """Stands in for MusicBrainz when rendering samples: every miss is a miss."""

    def get_artist(self, mbid):
        return None

    def search_artists(self, query):
        return []


def search_samples(query):
    q = (query or "").lower()
    return [
        {"id": s["id"], "name": s["name"], "type": "Group", "disambiguation": s["description"],
         "country": "GB", "years": None, "score": 100}
        for key, s in SAMPLES.items()
        if q and (q in key or q in s["name"].lower() or q in "demo sample")
    ]
