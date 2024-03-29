<div align="center">

## **THIS PROJECT IS CURRENTLY STILL UNDER ACTIVE DEVELOPMENT.<br>IN ITS CURRENT STATE IT IS INCOMPLETE, MESSY, BROKEN, AND INSECURE.**
    
<img align="right" src="assets/banner.png">

# [![GitHub release](https://img.shields.io/github/release/timraay/Bunker.svg)](https://github.com/timraay/Bunker/releases) [![GitHub license](https://img.shields.io/github/license/timraay/Bunker.svg)](https://github.com/timraay/Bunker/blob/main/LICENSE) [![GitHub contributors](https://img.shields.io/github/contributors/timraay/Bunker.svg)](https://github.com/timraay/Bunker/graphs/contributors) [![GitHub issues](https://img.shields.io/github/issues/timraay/Bunker.svg)](https://github.com/timraay/Bunker/issues) [![GitHub pull requests](https://img.shields.io/github/issues-pr/timraay/Bunker.svg)](https://github.com/timraay/Bunker/pulls) [![GitHub stars](https://img.shields.io/github/stars/timraay/Bunker.svg)](https://github.com/timraay/Bunker/stargazers)

</div>

<img align="right" width="250" height="250" src="assets/icon.png">

> For any issues or feature requests, please [open an Issue](https://github.com/timraay/Bunker/issues) here on GitHub, or [ask in Discord](https://discord.gg/Pm5WfhB). Bunker staff cannot unban you, see the FAQ below on where to appeal.

The Hell Let Loose Bunker is a service by server admins for server admins, to protect their servers from cheaters and troublemakers through collaborative data sharing. Receive reports created by verified admins and apply bans with a single button press through seamless integration with your favorite admin tools.

Only verified communities can use Bunker. Visit [the Server Hosting Discord](https://discord.gg/Pm5WfhB) to register your community.

## Setting up your community

### Prerequisites

Before setting up your community to receive reports, make sure you have the following;
- You are the owner of a registered community. You can register in [the Server Hosting Discord](https://discord.gg/Pm5WfhB).
- You have Manage Server rights on the Discord server you want to receive reports in.

### Steps

1. #### Invite HLL Bunker to your Discord server.

    Use [this link](https://discord.com/oauth2/authorize?client_id=1190718626286813244&scope=bot+applications.commands&permissions=35840) (TODO: Update permissions) to invite the Discord bot. Allow it all the requested permissions. Bunker won't be able to operate properly without them.

2. #### Configure which channel reports need to be sent to.

    Use the `/set-reports-channel` command in your Discord server to assign a text channel. Make sure that it is a **private** channel. Anyone that is able to read the channel will be able to respond to reports and (un)ban players!

3. #### Link up your admin tools.

    Use the `/manage-integrations` command, then press the `Add integration...` button. Select the type of admin tool you're trying to integrate and fill in the required details.

## Frequently Asked Questions (FAQ)

### Who reviews reports?

When a report is made, each community individually decides whether to ban the player or not. Players are never banned on your server without manual approval from your own admins. Do note that when a report is revoked, all subsequent bans will automatically be revoked - without requiring approval.

### I have been banned! What now?

If you have been banned as a result of a Bunker report (which the message should clearly state), it means a community has put forward evidence against you. The admins of the server you just tried to join has reviewed this evidence and decided to ban you. This means you are likely to be banned on multiple servers, and not just this one you tried to join.

When appealing your ban, you should first reach out to the community that created the original report. If they accept your appeal, they can revoke the report and get all subsequent bans from the other servers removed.

That being said, you can still reach out to each individual community. While they cannot remove your ban from other servers, if enough communities unban you, the report can also be revoked that way.

### As an admin, can I transfer ownership to myself?

In normal circumstances, only the existing owner can transfer ownership. Should the existing owner not be available to do so, please reach out to Bunker staff over on Discord.
