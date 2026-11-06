# Setup

Setup is done entirely via the [UI](https://my.home-assistant.io/redirect/config_flow_start/?domain=first_bus).

The integration is added **once**. The first time you add it you'll be asked for your first stop. Each stop is then shown as its own service underneath the single First Bus integration entry.

To track additional stops, go to the First Bus integration page and click **Add bus stop**. To change the name or buses of an existing stop, click the **⋮** menu next to the stop and choose **Reconfigure**. Stops can be deleted from the same menu.

!!! note

    If you are upgrading from a version where each stop was its own integration entry, your stops will automatically be merged into a single entry on startup. Existing entity ids and history are kept.

## Details

### Name

This is the name to help identify the stop. It will also be used as the name of the stop's service and in any created sensors.

### ATCO code

This identifies the stop that you're wanting to track. Instructions on how to find this, can be found in the [FAQ](./faq.md#how-do-i-find-my-atco-code). This can't be changed once the stop has been added.

### Buses

This is the list of buses that arrive at the designated stop that you're wanting to track. If you want any bus at the stop, leave this blank. If you are wanting multiple buses, then you will need to specify them in a comma separated list (e.g `19,20,21 A`). Matching is case insensitive and surrounding spaces are ignored.

## Entities

The full list of entities can be found in the [entities section](./entities.md).
