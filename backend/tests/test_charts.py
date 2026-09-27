from datetime import date

from app.charts import apply_chart, chart_members, find_timeline, name_key
from app.refiner import Refiner

# A made-up band's chart, in the shape Wikipedia's member charts take
WIKITEXT = """==Members==
Some prose.
==Timeline==
{{#tag:timeline|
DateFormat = dd/mm/yyyy
Period     = from:01/03/1970 till:{{#time:d/m/Y}}
Colors =
  id:vocals value:red    legend:Lead_vocals
  id:guitar value:green  legend:Guitars
  id:bass   value:blue   legend:Bass,_occasional_vocals
  id:drums  value:orange legend:Drums
  id:studio value:black  legend:Studio_album
  id:tour   value:yellow legend:Touring_musician
  id:era    value:black  legend:Band
BarData =
  bar:Ann   text:"[[Ann Able (musician)|Ann Able]]"
  bar:Bob   text:"Bob B. Baker"
  bar:Cy    text:Cy Cole
  bar:Dee   text:"Dee Dunn"
  bar:Eve   text:"Eve Early"
  bar:Gus   text:"Gus&nbsp;Gray †"
  bar:Hal   text:"Hal Hired"
  bar:Old   text:"The Old Band"
PlotData =
  width:11 textcolor:black
  color:vocals
  bar:Ann  from:start      till:end
  bar:Cy   from:01/06/1974 till:01/01/1976 width:3
  color:guitar
  bar:Bob  from:start      till:30/06/1974
  bar:Bob  from:01/01/1980 till:end
  bar:Bob  from:12/08/2026 till:13/08/2026
  bar:Cy   from:01/06/1974 till:01/01/1976
  color:bass
  bar:Dee  from:start      till:15/01/1978
  bar:Dee  from:01/02/1978 till:31/12/1979
  color:guitar
  bar:Eve  from:01/03/1975 till:10/03/1975
  bar:Gus  from:01/01/1985 till:01/01/1990
  color:tour
  bar:Hal  from:01/01/1985 till:01/01/1990
  color:era
  bar:Old  from:start      till:01/01/1978
}}
[[Category:Bands]]"""

TODAY = date(2026, 9, 27)


def _chart():
    return {m["name"]: m["stints"] for m in chart_members(find_timeline(WIKITEXT), today=TODAY)}


def test_an_unquoted_name_is_read_whole():
    assert "Cy Cole" in _chart()  # 'text:Cy Cole', as Whitesnake's chart writes them


def test_names_are_cleaned_of_markup_and_marks():
    assert "Gus Gray" in _chart()  # 'Gus&nbsp;Gray †'


def test_touring_hands_and_band_era_bars_are_not_members():
    chart = _chart()
    assert "Hal Hired" not in chart and "The Old Band" not in chart


def test_the_chart_is_found_in_the_article():
    src = find_timeline(WIKITEXT)
    assert src.strip().startswith("DateFormat") and "Category" not in src


def test_stints_come_out_to_the_day_with_open_ends():
    chart = _chart()
    assert chart["Ann Able"] == [{"begin": "1970-03-01", "end": None, "roles": ["lead vocals"]}]
    assert [(s["begin"], s["end"]) for s in chart["Bob B. Baker"]] == [("1970-03-01", "1974-06-30"),
                                                                      ("1980-01-01", None)]


def test_a_blip_is_left_out_and_a_short_break_is_no_break():
    chart = _chart()
    assert len(chart["Bob B. Baker"]) == 2  # the one-day 2026 "return" is a slip
    assert [(s["begin"], s["end"]) for s in chart["Dee Dunn"]] == [("1970-03-01", "1979-12-31")]


def test_a_combined_legend_is_one_instrument_each():
    assert _chart()["Dee Dunn"][0]["roles"] == ["bass", "vocals"]  # not the singer


def test_a_member_with_only_a_stand_in_spell_is_still_the_charts():
    assert _chart()["Eve Early"] == []  # nine days: nothing to draw


def test_the_thick_bar_is_the_principal_instrument():
    # Cy sang too (a thin bar), but played guitar: Tommy Bolin, not "vocals"
    assert _chart()["Cy Cole"][0]["roles"] == ["guitars", "lead vocals"]


def test_the_chart_takes_over_for_the_members_it_has():
    mb = [
        {"person_id": "p-ann", "person_name": "Ann Able", "band_id": "b", "band_name": "Band",
         "begin": "1970", "end": None, "ended": False, "attributes": ["original"]},
        {"person_id": "p-bob", "person_name": "Bob Baker", "band_id": "b", "band_name": "Band",
         "begin": "1970", "end": "1990", "ended": True, "attributes": ["vocals"]},
        {"person_id": "p-eve", "person_name": "Eve Early", "band_id": "b", "band_name": "Band",
         "begin": "1975", "end": "1976", "ended": True, "attributes": ["keyboards"]},
        {"person_id": "p-ann", "person_name": "Ann Able", "band_id": "other", "band_name": "Other",
         "begin": "1990", "end": None, "ended": False, "attributes": []},
    ]
    chart = chart_members(find_timeline(WIKITEXT), today=TODAY)
    got = apply_chart(mb, chart, "b", "Band")
    bob = [m for m in got if m["person_id"] == "p-bob"]  # "Bob B. Baker" on Wikipedia
    assert [(m["begin"], m["end"]) for m in bob] == [("1970-03-01", "1974-06-30"), ("1980-01-01", None)]
    assert bob[0]["attributes"][0] == "guitars"
    assert any(m["person_id"] == "wiki:" + name_key("Cy Cole") for m in got)  # not on MusicBrainz: added
    assert not any(m["person_id"] == "p-eve" for m in got)  # on the chart for nine days only: MusicBrainz's 1975-76 goes
    mb.append({"person_id": "p-fay", "person_name": "Fay Frost", "band_id": "b", "band_name": "Band",
               "begin": "1985", "end": "1986", "ended": True, "attributes": ["piano"]})
    assert not any(m["person_id"] == "p-fay" for m in apply_chart(mb, chart, "b", "Band"))  # in its years, not on it: not a member
    mb.append({"person_id": "p-gus", "person_name": "Gus Gone", "band_id": "b", "band_name": "Band",
               "begin": "1965", "end": "1968", "ended": True, "attributes": ["drums"]})
    mb.append({"person_id": "p-kidd", "person_name": "Kid Band", "band_id": "b", "band_name": "Band",
               "begin": "1985", "end": None, "ended": False, "attributes": ["eponymous"]})
    kept = {m["person_id"] for m in apply_chart(mb, chart, "b", "Band")}
    assert "p-gus" in kept   # before the chart's years: MusicBrainz's word stands
    assert "p-kidd" in kept  # the band's named after him
    assert any(m["band_id"] == "other" for m in got)    # other bands untouched
    assert "original" in [a for m in got if m["person_id"] == "p-ann" for a in m["attributes"]]


def test_the_refiner_draws_the_line_ups_from_the_chart():
    chart = chart_members(find_timeline(WIKITEXT), today=TODAY)
    records = {
        "b": {"mbid": "b", "name": "Band", "type": "Group", "begin": "1970", "end": None, "ended": False,
              "chart": chart, "memberships": [
                  {"person_id": "p-cy", "person_name": "Cy Cole", "band_id": "b", "band_name": "Band",
                   "begin": "1974", "end": "1976", "ended": True, "attributes": ["lead vocals"]}]},
    }
    harvest = {"root_id": "b", "root_name": "Band", "root_bands": ["b"], "band_levels": {"b": 0},
               "records": records}
    band = Refiner(today=2026.7).build(harvest).bands["b"]
    cy = [s for s in band.stints if s.person_id == "p-cy"]
    assert cy and cy[0].roles[0] == "guitar"
    assert {s.name for s in band.stints} >= {"Ann Able", "Bob B. Baker", "Dee Dunn"}


def test_colour_names_are_not_case_sensitive():
    src = find_timeline(WIKITEXT).replace("color:bass", "color:Bass")
    assert "Dee Dunn" in {m["name"] for m in chart_members(src, today=TODAY)}


def test_a_short_first_name_is_the_same_musician():
    mb = [{"person_id": "p-rob", "person_name": "Robert Bobbins", "band_id": "b", "band_name": "Band",
           "begin": "1970", "end": None, "ended": False, "attributes": ["drums"]}]
    chart = [{"name": "Bob Bobbins", "stints": []}, {"name": "Bobby Bobbins", "stints": []}]
    from app.charts import _by_surname
    assert _by_surname({"robertbobbins": mb}, "Rob Bobbins") == mb
    assert _by_surname({"robertbobbins": mb}, "Rhonda Bobbins") is None
