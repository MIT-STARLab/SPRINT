# Defining satellite orbits in the Constellation Configuration.

Valid entries in constellation_config.json, (for a particular case), 
  in constellation_definition > constellation_params > orbit_params > sat_orbital_elems

### Definition by Plane
In this case you define each plane of sats in a constellation, by giving the shape of the orbit and the count and position of the sats within the orbit.  This is for ease of definition: early in the sim, this is automatically broken into the individual format.
```
{
  "def_type":"plane",
  "orbit_indx"    : 0,
  "plane_def": {
      "a_km"          : 7378,
      "e"             : 0,
      "i_deg"         : 97.86,
      "RAAN_deg"      : 0,
      "arg_per_deg"   : 0
  },

  "first_M_deg"   : 90,               "_comment1" : "anomaly of first sat, which subsequent will follow",
  "spacing_type"  : "progressive",    "_comment2" : "spacing: 'even', or 'progressive', or 'set'; indicate whether the sats in the plane are evenly spaced (val ignored/not needed), or should space progressively by the subsequently provided 'spacing_val', or should fix each to a anomoly in a set (array) to allow arbitrary values ",
  "spacing_val"   : 90,               "_comment3" : "for example, this combo would result in 3 sats in this plane, with the first at 90 deg anomaly, followed by 2 more at 180 and 270."

  "first_sat_id"  : 0,                "_comment4" : "the comnbo of first_sat_id, and sats_in_plane must not result in conflicting indices, and should be 'in order' without gaps, and in total match 'num_satellites' and 'sat_ids' field above. Sorry for the restrictions for now, will make a validation function.",
  "sats_in_plane" : 3,

   "propagation_method": "matlab_delkep"
}
```

### Definition by individual enumeration
In this case it is required to list each satellite and its elements individually.  This matches the "original" format given by CIRCINUS, excepting the addition of the "def_type" field.
```
{
    "sat_id": "S0",
    "def_type":"indv",
    "kepler_meananom": {
        "a_km":  7378,
        "e": 0,
        "i_deg": 97.86,
        "RAAN_deg": 0,
        "arg_per_deg": 0,
        "M_deg": 90
    },
    "propagation_method": "matlab_delkep"
},
```

### Definition by constellation type
There exist expansions for descriptions of "Walker" constellations, but these will need to be updated to not catch on assertions around the prior two here. Walker constellations can also be specified by the above plane-wise definition.