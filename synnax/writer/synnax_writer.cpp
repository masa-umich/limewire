/*
Outline:
Class SynnaxWriter
Make a connection to the Synnax Server
Make an amount of channels for GSE on Synnax
Make an amount of channels for FC on Synnax
Make a thread for the writer so it can work asynchronously
Save the initial state of the system to a file so it can be restored if the system crashes
API:
Take in a 32bit selection bitmask and a 32bit state bitmask from the FC and write it to the appropriate synnax channels
Take a in a valve channel selection from the GSE driver and send it to the correct GSE synnax channels
*/