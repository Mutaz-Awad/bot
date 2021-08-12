import base64
import json
from datetime import datetime
from os import environ
from urllib.parse import urlunparse

import discord
from bot import checks, cmd, converter
from bot.utils import get_command_signature
from discord.ext import commands


class Utilities(cmd.Cog):
    """Message helpers"""

    async def get_short_url(self, url):
        async with self.session.post(
            "https://share.discohook.app/create", json={"url": url}
        ) as resp:
            if resp.status >= 400:
                return None, None

            data = await resp.json()
            url = data["url"]
            expires = datetime.fromisoformat(data["expires"])

            return url, expires

    def get_message_data(self, message: discord.Message):
        data = {
            "content": message.content or None,
            "embeds": [],
        }

        for embed in message.embeds:
            if embed.type != "rich":
                continue

            embed_dict = embed.to_dict()

            embed_dict.pop("type")
            embed_dict.get("image", {}).pop("proxy_url")
            embed_dict.get("image", {}).pop("width")
            embed_dict.get("image", {}).pop("height")
            embed_dict.get("thumbnail", {}).pop("proxy_url")
            embed_dict.get("thumbnail", {}).pop("width")
            embed_dict.get("thumbnail", {}).pop("height")
            embed_dict.get("author", {}).pop("proxy_icon_url")
            embed_dict.get("footer", {}).pop("proxy_icon_url")

            data["embeds"].append(embed_dict)

        if len(data["embeds"]) <= 0:
            data.pop("embeds")

        return data

    @commands.group(invoke_without_command=True, require_var_positional=True)
    @commands.cooldown(3, 30, type=commands.BucketType.user)
    @checks.sensitive()
    async def restore(self, ctx: cmd.Context, *messages: converter.MessageConverter):
        """Sends a Discohook link for a given Discord message link"""

        data = {"messages": []}
        for message in messages:
            data["messages"].append(
                {
                    "data": self.get_message_data(message),
                }
            )

        data_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        data_b64 = base64.urlsafe_b64encode(data_json.encode()).decode().strip("=")
        url = urlunparse(("https", "discohook.app", "/", "", f"data={data_b64}", ""))

        short_url, timestamp = await self.get_short_url(url)

        if short_url is None:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Error",
                    description="Failed to get short URL",
                )
            )
            return

        embed = discord.Embed(
            title="Message",
            description=short_url,
        )
        embed.set_footer(text="Expires")
        embed.timestamp = timestamp
        await ctx.prompt(embed=embed)

    @restore.command(name="edit", require_var_positional=True)
    @commands.cooldown(3, 30, type=commands.BucketType.user)
    @commands.has_guild_permissions(manage_webhooks=True)
    @checks.sensitive()
    async def restore_edit(
        self, ctx: cmd.Context, *messages: converter.MessageConverter
    ):
        """Sends a Discohook link for a given Discord message link with extra fields filled for faster editing."""

        webhook_ids = {message.webhook_id for message in messages}
        if len(webhook_ids) > 1:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Error",
                    description="The messages must not be sent by different webhooks.",
                )
            )
            return
        webhook_id = next(iter(webhook_ids))
        if not webhook_id:
            plural_message = "message is" if len(messages) == 1 else "messages are"
            await ctx.prompt(
                embed=discord.Embed(
                    title="Error",
                    description=f"The {plural_message} not sent by webhooks.",
                )
            )
            return
        webhook = None
        try:
            webhook = await ctx.bot.fetch_webhook(webhook_id)
        except discord.NotFound:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Webhook Deleted",
                    description="The webhook that was used to send the message was deleted.",
                )
            )
            return
        except discord.Forbidden:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Missing Permissions",
                    description=f"I don't have have permission to manage webhooks in the webhook's channel.",
                )
            )
            return

        data = {"messages": [], "targets": [{"url": webhook.url}]}
        for message in messages:
            data["messages"].append(
                {
                    "data": self.get_message_data(message),
                    "reference": message.jump_url,
                }
            )

        data_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        data_b64 = base64.urlsafe_b64encode(data_json.encode()).decode().strip("=")
        url = urlunparse(("https", "discohook.app", "/", "", f"data={data_b64}", ""))

        short_url, timestamp = await self.get_short_url(url)

        if short_url is None:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Error",
                    description="Failed to get short URL",
                )
            )
            return

        try:
            embed = discord.Embed(
                title="Message",
                description=short_url,
            )
            embed.set_footer(text="Expires")
            embed.timestamp = timestamp
            await ctx.author.send(embed=embed)
            await ctx.prompt(
                embed=discord.Embed(
                    title="Message URL sent",
                    description="Because the webhook URL should be kept secret, a message has been sent to your DMs.",
                )
            )
        except discord.Forbidden:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Forbidden",
                    description="Could not send DM, check server privacy settings or unblock me.",
                )
            )

    @commands.command()
    @commands.cooldown(4, 4, commands.BucketType.member)
    async def big(self, ctx: cmd.Context, *, emoji: converter.PartialEmojiConverter):
        """Gives the URL to a custom emoji"""

        embed = discord.Embed(
            title=f"Emoji URL for :{emoji.name}:", description=str(emoji.url)
        )
        embed.set_image(url=str(emoji.url))
        embed.set_footer(text=f"ID: {emoji.id}")

        await ctx.prompt(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.cooldown(4, 4, commands.BucketType.member)
    async def avatar(self, ctx: cmd.Context, *, user: discord.User = None):
        """Gives the URL to a user's avatar"""

        if not user:
            user = ctx.author

        url = str(user.avatar_url_as(static_format="png", size=4096))

        embed = discord.Embed(title=f"Avatar URL for @{user}", description=url)
        embed.set_image(url=url)
        embed.set_footer(text=f"ID: {user.id}")

        await ctx.prompt(embed=embed)

    @avatar.command(name="static")
    @commands.cooldown(4, 4, commands.BucketType.member)
    async def avatar_static(self, ctx: cmd.Context, *, user: discord.User = None):
        """Gives the URL to a user's non-animated avatar"""

        if not user:
            user = ctx.author

        url = str(user.avatar_url_as(format="png", size=4096))

        embed = discord.Embed(title=f"Avatar URL for @{user}", description=url)
        embed.set_image(url=url)
        embed.set_footer(text=f"ID: {user.id}")

        await ctx.prompt(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.cooldown(4, 4, commands.BucketType.member)
    @commands.guild_only()
    async def icon(self, ctx: cmd.Context):
        """Gives the URL to the server's icon"""

        url = str(ctx.guild.icon_url_as(static_format="png", size=4096))

        embed = discord.Embed(title=f"Icon URL for {ctx.guild}", description=url)
        embed.set_image(url=url)
        embed.set_footer(text=f"ID: {ctx.guild.id}")

        await ctx.prompt(embed=embed)

    @icon.command(name="static")
    @commands.cooldown(4, 4, commands.BucketType.member)
    @commands.guild_only()
    async def icon_static(self, ctx: cmd.Context):
        """Gives the URL to the server's non-animated icon"""

        url = str(ctx.guild.icon_url_as(format="png", size=4096))

        embed = discord.Embed(title=f"Icon URL for {ctx.guild}", description=url)
        embed.set_image(url=url)
        embed.set_footer(text=f"ID: {ctx.guild.id}")

        await ctx.prompt(embed=embed)


def setup(bot):
    bot.add_cog(Utilities(bot))
