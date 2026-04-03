# WMPL Upgrades
by Mark McIntyre, April 2026

## Key points

- Added new operation mode to create candidates.
- Added distributed processing for candidates.
- Added checks for duplicate transactions.
- Replaced JSON database with SQLite databases.
- Slight change to command-line options.

### Operation Modes

The updated solver now has three core operational modes, numbered 4, 1, and 2. In the code these are MCMODE_CANDS, MCMODE_PHASE1 and MCMODE_PHASE2. The previous mode 1 has been split into two stages numbered 4 and 1 as explained below. 

Here's what each phase does.

- In mcmode 4, the solver finds and saves candidate groups of observations.  
   During this phase, unpaired observations are loaded and candidate groups found. Observations are excluded if they're already marked as paired in the observations database, and potential candidate groups are also checked against the candidate database to avoid reanalysing combinations that were already found. Remaining new candidates are then added to the candidate database and saved to disk.

- In mcmode 1, the solver loads candidates created by the previous step and attempts to find a simple solution. 
If successful, the trajectory is saved to disk and a copy placed in the 'phase1' folder for further analysis, while the trajectory and observations databases are updated accordingly. If unsuccessful, the trajectory is added to the list of failed trajectories in the trajectories database.

- In mcmode 2, the solver loads phase1 solutions and performs Monte-Carlo analysis. This mode is unchanged from previously.

Some Bitwise combinations of modes are permitted as shown in the table below:

| Value               | Effect                                                       | Example Use                                 |
| ------------------- | ------------------------------------------------------------ | ------------------------------------------- |
| 3 <br>MCMODE_SIMPLE | Runs modes 1+2, i.e. loads and fully solves candidates.      | UKMON currently uses this mode.             |
| 5 <br>MCMODE_BOTH   | Runs modes 4+1, i.e. creates phase 1 solutions from scratch. | GMN currently uses this mode.               |
| 7 <br>MCMODE_ALL    | Equivalent to 0 or passing no mcmode                         | Typically used during manual data analysis. |
| Any other value     | Treated as a value of 7                                      |                                             |

Note that in modes 0, 3, 5 and 7, intermediate files (ie candidates and phase1 files) are not saved to disk. 

### Distributed Processing

The solver supports distribution of both candidates and phase1 solutions to child nodes.

To enable distributed processing, we require one master node and one or more child nodes.

On the master, we create a configuration file '**wmpl_remote.cfg**' in the same folder as the databases and then run three instances of the Solver on a master node, one in each of mcmodes 4, 1 and 2 (more than one instance in mcmode 2 can be run). The content of the configuration file is explained below and a sample file is included in the repository.

On each child, we also create a configuration file (see 'Child Node Configuration' below). Child nodes can run in mcmodes 1 or 2, collecting relevant data from the master node and uploading the results back.

SFTP is used to move data between master and child, and each child must therefore have an SFTP account on the server hosting the master.

Data are written into a 'files' folder in the sftp account's home directory, and therefore the account running the master instances of the solver must be able to read from, write to and create folders in a "files" directory in the children's home directories. On my test server I achieved this with POSIX ACLs and Unix group membership.

Additionally, the solver itself sets permissions on files and subfolders, and these should not be altered.

The required folder structure for one node is shown below.

![image](node_structure.png)

**Master Node Configuration**

The configuration file for the master node specifies the child nodes that are available, the capacity of each node, and the mcmode that its operating in (modes 1 or 2, no other mcmode is supported). The capacity value can be any integer, with zero meaning the node is disabled and any negative value meaning the node has no capacity limit.

When running in master mode, the instance in mcmode 4 will distribute candidates and the instance in mcmode 1 will distribute phase1 pickle files, provided suitable child nodes are configured.

Example master-mode configuration file:

\[mode\]  
mode = master  
\[children\]  
node1 = /home/node1, 600, 1  
node2 = /home/node2, 500, 2  
node3 = /home/node3, 0, 1

This indicates that:

- node 1 is running in mcmode 1 and has capacity of 600.
- node 2 is running in mcmode 2 and has capacity of 500.
- Node 3 is currently disabled (capacity zero) and will not be assigned data.

If we bring node 3 online, we can change the capacity from zero to some suitable value, and the master will begin assigning candidates to it (see 'Dynamically Adding Nodes' below).

If no nodes are available, or if all nodes are at capacity, any remaining data will be assigned to the master node.

The master will also stop assigning data to a node if a special file named "stop" is present in the files folder of the child's SFTP home directory. The child nodes create this file when shutting down but it can also be created manually.

Furthermore, if data has not been picked up by a child within six hours, then it will be reassigned to the master node. This ensures that data is left unprocessed if for example a node crashes unexpectedly.

**Dynamically Adding Nodes**

The master instance of the solver re-reads the remote configuration file on each loop, and so nodes can be added, removed, disabled or enabled on demand, without needing to restart the master.

So, for example, one could create a configuration listing several child nodes with capacity set to zero, which would mean they were initially disabled and so the Solver would assign all candidates to the master node. However, if volumes rose, an instance of the solver could be started up on a child node and the master configuration file updated. On the master node's next loop, data would be automatically assigned to the children.

You can also _manually_ move files between child node folders on the server. For instance, if you want to move some load from node1 to node2 you can move some of the candidate files from node1's _candidates_ folder to node2's _candidates_ folder. A UNIX command to do this might be

_ls -1 ~node/files/candidates | head -100 | while read i ; do mv \$i ~node2/files/candidates; done_

**Processing Uploaded Data**

Upon each loop round, the master node will scan each node's home directory for uploaded results. These will be integrated into the trajectories data, and the databases updated.

**Child Node Configuration**

The child must be running in mcmode 1 or 2 - no other mode is supported at present.

The child configuration file specifies the server, user and key to use for connections to the master node. Port is optional but can be specified if a non-standard SFTP port is in use.

\[mode\]  
mode = child  
<br/>\[children\]  
host = testserver.somewhere.com  
user = node1  
key = ~/.ssh/somekey  
port = 22

At startup, the child node will connect to the master and remove the "stop" file, if present. This indicates to the master that it is "open for business". The child will then loop around, downloading any assigned data and processing it. Downloaded files are moved to a subfolder _processed_ on the sftp server. Upon completion it will upload the results to the sftp server.

**Stopping a Child Node**

Any node can be terminated by pressing Ctrl-C or by sending SIGINT to its process. The node will stop processing immediately and create a "stop" file on the sftp server.

Note that termination will leave data incompletely processed and no upload will take place, and so it is advisable to wait until the child's logfile indicates it is idle.

Alternatively, one can identify the most recent, potentially incomplete, data set that was assigned to the node by looking in the child's _processed_ folders and copying the data back to the master node's _candidate_ or _phase1_ folders as appropriate.

**Recovering from a Child Node Crash or Shutdown**

If a child node crashes or is otherwise terminated during processing, the data can be recovered and redistributed to the master or other nodes, or indeed to the failed node after it has restarted. This can be done by looking in the _processed_ folders on the child, or if the child node is unavailable, in the child node's _processed_ folder on the master node, identifying the most recent data, and moving it as necessary.

## Duplicate Transaction Checks

A check has been introduced in both candidate finding and phase1 solving that examines the database for potential duplicate or mergeable trajectories.

Duplicates are defined as trajectories that contain the same observations. When detected, the solution with the least ignored observations is retained and the duplicates are deleted.

Mergeable trajectories are defined as those with at least one common observation. In principle these should never arise but in practice with a distributed processing model, it is possible. For example, a candidate might be found and handed off for solving but while it is still being solved, a new observation might be uploaded by a camera, and so on its next pass the candidate finder creates a second candidate with an additional observation and a different reference timestamp. When detected the mergeable trajectories are deleted and all observations are marked unpaired, so that on its next pass the candidate finder should identify a single combined candidate.

## Databases

The JSON database has been replaced by three SQLite databases, one for Observations, one for Trajectories and one for Candidates.

This approach was taken because most database writing takes place during phase 1 solving, but some takes place during candidate finding notably when reprocessing previous trajectories with new observations. By splitting the databases, we minimise potential concurrent write situations. SQLite does not support multiple simultaneous writes, and though it will back off and retry after a few milliseconds, it is preferrable to avoid unnecessary delays.

**If The Solver Crashes**

Although most operations are immediately committed to the databases, it is possible for the solver to crash and leave an incomplete transaction. This will be revealed by the existence of write-ahead logs in the database directory e.g. "observations.db-wal".

If this file is present, then upon next startup, SQLite will complete any pending transactions. This minimises the risk of data loss, but at worst may lead to observations being reprocessed. This is preferable to trajectories being missed.

**The Legacy JSON database**

The legacy JSON database is no longer used It is not deleted however, after an initial data migration described below it is no longer being used and can be moved to long-term storage if desired.

**Initial Population of SQLite**

When the Solver is started up, it checks for the existence of the new databases. If they are not present, it creates them and prepopulates them with the last few days of data from the old JSON database if available. For example, if run with the auto flag and default period of 5 days lookback, the last five days of data will be copied to SQLite. This ensures that sufficient observation and failed trajectory data is present for normal operation of the solver.

The JSON database is then closed and is not referred to again even on subsequent runs of the solver. It is not truncated, archived or deleted and remains as an historical record of the state of the database as at the cutover date.

**Historic Reruns**

If the solver is rerun for an historic period from before the cutover, there will be no paired observations or failed trajectories data in the databases. The assumption is that if we are rerunning for an historic period, we are either looking to integrate new observations into the dataset or to recalculate trajectories using improved mathematical models. In either case it seems likely we'd want to start by reanalysing the raw data.

That said, should we wish to copy historical data into the SQLite databases, this can be done with the command-line interface to CorrelateDB as shown below:

_python -m wmpl.Trajectory.CorrelateDB --dir_path rms_data --action copy --timerange "(20251215-000000,20251222-000000)"_

This will copy observations and failed trajectories into SQLite from the JSON database in _rms_data_ for a date range 2025-12-15 to 2025-12-22, creating the SQLite databases if necessary.

This is quite a slow operation - on my 4-core i7 desktop it takes about several minutes to copy a week's worth of data.

## Command Line Options

One option has been removed and two new options added

Removed:

- \--**remotehost**: this has been superseded by the remote configuration file

Added:

- \--**addlogsuffix**: default false - this adds a suffix to the logfile to indicate which phase is being run.  
   For example, with this flag passed, the logfile for a run in MCMODE*CANDS would be something like \_correlate_rms_20260214_121314_cands.log* whereas a phase-1 log file would be _correlate_rms_20260214_121314_simple.log_.

- **\--archivemonths:** default 3: this specifies the number of months' data to keep in the databases. Data older than this number of months will be archived. A value of zero means keep everything. This flag is useful during testing or when rerunning for an historical data when you might not want to remove older data.