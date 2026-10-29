---
name: connectors
description: Work with the client's data connectors - each connector is one table in the organization's datasets schema.
---

# Connectors

Each connector is a table in the organization's datasets schema, such as Meta Ads or Google Ads. List the connectors with `list_connectors` before choosing data, then ask the user which connector and channels to use. Use `list_channels_within_connector` (needs approval) or `list_channels` to read a connector's channels.
