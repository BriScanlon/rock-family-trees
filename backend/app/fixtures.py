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

SAMPLES = {
    "yardbirds": {
        "id": "demo:yardbirds",
        "name": "The Yardbirds (demo)",
        "description": "Offline sample: The Yardbirds and the bands they spawned. Dates are approximate.",
        "default_depth": 3,
    }
}


def _pid(key):
    return f"demo:person:{key}"


def _bid(key):
    return f"demo:{key}" if key == "yardbirds" else f"demo:band:{key}"


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
