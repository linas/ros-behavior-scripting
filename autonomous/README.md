
Autonomous Behaviors
====================

The code in this directory handles certain perception-reaction cycles
autonomously.  These are loops where the opencog cogserver does not 
get involved in the processing.

Running
-------
Just start `main.py` in this directory.

Control
-------
Enable behaviors by publishing:
```
	rostopic  pub --once behavior_switch std_msgs/String "btree_on"
```

Disable behaviors by publishing:
```
	rostopic  pub --once behavior_switch std_msgs/String "btree_off"
```
