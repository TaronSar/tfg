What the encounter generator tool does:
 - It generates encounters between the ownship and an intruder
 - It allow selection of ownship and intruder characteristics
 - It generates encounters 3 different ways:
   1) From aircraft parameters (speeds, altitudes, etc.)
      See the first example in test_generate_single_encounter.py
      These encounters are generated using an Air Transport Canada tool based on observations
      of multiple classes of aircraft, and encoded into a bayesian tool to generate flights.
      There is a way to just generate trajectories for each aircraft category in the tool by
      using test_generate_trajectories.py
   2) From saved csv files extracted from OpenStreetMap features like rivers, railways, etc.
      See the second example in test_generate_single_encounter.py for usage of csv files
      See test_generate_osm_feature_routes.py for generation of these routes
   3) From saved csv files representing search patterns
      See the second example in test_generate_single_encounter.py fo rusage of csv files
      See test_generate_search_pattern_routes.py for generation of these routes
 - It allows for parameter combinations to be used to generate multiple encounters
   See test_generate_multiple_encounters.py and generate_encounters.py for an example of use
   and an example of how to generate the combinations to be tested. The combinations can be
   generated from a cartesian product of parameters for each input, or can also have a Monte
   Carlo random component. See the comments on generate_encounters.py for a description.

How to use the trajectory generator tool:
 - Once the parametric definition, or csv file is selected, routes can be used 
   in 3 different ways. See test_generate_multiple_encounters.py for examples:
   1) plotting the routes.
   2) getting a python generator to include in your code, where every call generates a new encounter.
   3) generating an hdf5 file with the encounter data, which can then be extracted one by one.

 