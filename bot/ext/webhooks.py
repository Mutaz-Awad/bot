import asyncio

import discord
from bot import cmd, converter, menus
from bot.utils import get_command_signature, wrap_in_code
from discord.ext import commands


class Webhooks(cmd.Cog):
    """Webhook management"""

    def get_webhook_embed(
        self,
        ctx: cmd.Context,
        webhook: discord.Webhook,
        *,
        message=None,
        show_url=False,
    ):
        embed = discord.Embed(
            title=f"{message}: {webhook.name}" if message else webhook.name
        )
        embed.set_thumbnail(url=str(webhook.avatar_url))

        embed.add_field(name="Channel", value=webhook.channel.mention)
        embed.add_field(
            name="Created at",
            value=f"{webhook.created_at.ctime()} UTC".replace("  ", " "),
        )

        if webhook.token:
            url_message = (
                webhook.url
                if show_url
                else f"Use {get_command_signature(ctx, self.webhook_url)} to obtain the URL."
            )
        else:
            url_message = "This webhook was created by a bot other than myself, so I cannot get its full URL."
        embed.add_field(name="Webhook URL", value=url_message, inline=False)

        return embed

    @commands.group(invoke_without_command=True)
    @commands.cooldown(4, 4, commands.BucketType.member)
    @commands.has_guild_permissions(manage_webhooks=True)
    @commands.bot_has_guild_permissions(manage_webhooks=True)
    async def webhook(self, ctx: cmd.Context):
        """Group of commands to manage webhooks"""
        await ctx.send_help("webhook")

    @webhook.command(name="list")
    @commands.cooldown(4, 4, commands.BucketType.member)
    @commands.has_guild_permissions(manage_webhooks=True)
    @commands.bot_has_guild_permissions(manage_webhooks=True)
    async def webhook_list(self, ctx: cmd.Context, channel: discord.TextChannel = None):
        """Lists webhooks for the server or a given channel"""

        if channel:
            channel_perms = channel.permissions_for(ctx.me)
            if not channel_perms.view_channel or not channel_perms.manage_webhooks:
                raise commands.BotMissingPermissions(["manage_webhooks"])

        embed = discord.Embed(
            title="Webhooks",
            description=f"Use {get_command_signature(ctx, self.webhook_get)}"
            " to get more info on a webhook.",
        )
        embed.set_footer(
            text="Page {current_page}/{total_pages}, "
            "showing webhook {first_field}..{last_field}/{total_fields}."
        )
        paginator = menus.FieldPaginator(self.bot, base_embed=embed)

        for webhook in await ctx.guild.webhooks():
            if webhook.type != discord.WebhookType.incoming:
                continue
            if channel and webhook.channel_id != channel.id:
                continue

            paginator.add_field(
                name=webhook.name,
                value=f"Channel: {webhook.channel.mention}\nID: {webhook.id}",
            )

        await paginator.send(ctx)

    @webhook.command(name="get", aliases=["show"])
    @commands.cooldown(3, 8, commands.BucketType.member)
    @commands.has_guild_permissions(manage_webhooks=True)
    @commands.bot_has_guild_permissions(manage_webhooks=True)
    async def webhook_get(
        self,
        ctx: cmd.Context,
        channel: converter.Never,
        *,
        webhook: converter.WebhookConverter,
    ):
        """Shows data for a given webhook"""

        channel_perms = webhook.channel.permissions_for(ctx.me)
        if not channel_perms.view_channel or not channel_perms.manage_webhooks:
            raise commands.BotMissingPermissions(["manage_webhooks"])

        await ctx.prompt(embed=self.get_webhook_embed(ctx, webhook))

    @webhook.command(name="url")
    @commands.cooldown(3, 8, commands.BucketType.member)
    @commands.has_guild_permissions(manage_webhooks=True)
    @commands.bot_has_guild_permissions(manage_webhooks=True)
    async def webhook_url(
        self,
        ctx: cmd.Context,
        channel: converter.Never,
        *,
        webhook: converter.WebhookConverter,
    ):
        """Obtains the URL for a given webhook"""

        channel_perms = webhook.channel.permissions_for(ctx.me)
        if not channel_perms.view_channel or not channel_perms.manage_webhooks:
            raise commands.BotMissingPermissions(["manage_webhooks"])

        if not webhook.token:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Unable to get URL",
                    description="This webhook was created by a bot other than myself, so I cannot get its full URL.",
                )
            )
            return

        try:
            await ctx.author.send(
                embed=self.get_webhook_embed(ctx, webhook, show_url=True)
            )
            await ctx.prompt(
                embed=discord.Embed(
                    title="Webhook URL sent",
                    description="Because the URL should be kept secret, a message has been sent to your DMs.",
                )
            )
        except discord.Forbidden:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Forbidden",
                    description="Could not send DM, check server privacy settings or unblock me.",
                )
            )

    @webhook.command(name="new", aliases=["add", "create"])
    @commands.cooldown(3, 30, commands.BucketType.member)
    @commands.has_guild_permissions(manage_webhooks=True)
    @commands.bot_has_guild_permissions(manage_webhooks=True)
    async def webhook_new(
        self, ctx: cmd.Context, channel: discord.TextChannel, *, name: str
    ):
        """Creates a new webhook for a given channel"""

        channel_perms = channel.permissions_for(ctx.me)
        if not channel_perms.view_channel or not channel_perms.manage_webhooks:
            raise commands.BotMissingPermissions(["manage_webhooks"])

        if len(name) > 80:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Webhook name too long",
                    description="Webhook names can only be up to 80 characters long",
                )
            )
            return

        avatar_file = (
            await ctx.message.attachments[0].read()
            if len(ctx.message.attachments) > 0
            else None
        )

        webhook = await channel.create_webhook(name=name, avatar=avatar_file)

        await ctx.prompt(
            embed=self.get_webhook_embed(ctx, webhook, message="New webhook created")
        )

    @webhook.command(name="edit", aliases=["rename", "avatar"])
    @commands.cooldown(3, 30, commands.BucketType.member)
    @commands.has_guild_permissions(manage_webhooks=True)
    @commands.bot_has_guild_permissions(manage_webhooks=True)
    async def webhook_edit(
        self,
        ctx: cmd.Context,
        channel: converter.Never,
        webhook: converter.WebhookConverter,
        new_name: str = None,
    ):
        """Edits an existing webhook

        If webhook names contains spaces, it must be in quotes.
        To edit the avatar, attach a image file with the message.
        """

        channel_perms = webhook.channel.permissions_for(ctx.me)
        if not channel_perms.view_channel or not channel_perms.manage_webhooks:
            raise commands.BotMissingPermissions(["manage_webhooks"])

        if not webhook.token:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Unable to edit",
                    description="This webhook was created by a bot other than myself, so I cannot edit it.",
                )
            )
            return

        edit_kwargs = {}

        if new_name:
            edit_kwargs["name"] = new_name

            if len(new_name) > 80:
                await ctx.prompt(
                    embed=discord.Embed(
                        title="Webhook name too long",
                        description="Webhook names can only be up to 80 characters long",
                    )
                )
                return

        if len(ctx.message.attachments) > 0:
            edit_kwargs["avatar"] = await ctx.message.attachments[0].read()

        if len(edit_kwargs.keys()) <= 0:
            raise commands.UserInputError("No new name or avatar was given")

        await webhook.edit(**edit_kwargs)

        webhook = await self.bot.fetch_webhook(webhook.id)
        await ctx.prompt(
            embed=self.get_webhook_embed(ctx, webhook, message="Webhook edited")
        )

    @webhook.command(name="delete", aliases=["remove"])
    @commands.cooldown(3, 30, commands.BucketType.member)
    @commands.has_guild_permissions(manage_webhooks=True)
    @commands.bot_has_guild_permissions(manage_webhooks=True)
    async def webhook_delete(
        self,
        ctx: cmd.Context,
        channel: converter.Never,
        *,
        webhook: converter.WebhookConverter,
    ):
        """Deletes a given webhook

        Messages sent by this webhook will not be deleted.
        """

        channel_perms = webhook.channel.permissions_for(ctx.me)
        if not channel_perms.view_channel or not channel_perms.manage_webhooks:
            raise commands.BotMissingPermissions(["manage_webhooks"])

        if not webhook.token:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Unable to delete",
                    description="This webhook was created by a bot other than myself, so I cannot delete it.",
                )
            )
            return

        prompt = menus.ConfirmationPrompt(
            self.bot,
            embed=discord.Embed(
                title="Confirmation",
                description=f"Are you sure you want to delete {wrap_in_code(webhook.name)}?"
                " This action cannot be reverted.",
            ),
        )

        prompt.action_confirm = "\N{WASTEBASKET}"

        if await prompt.send(ctx):
            await webhook.delete()

            await ctx.prompt(
                embed=discord.Embed(
                    title="Webhook deleted",
                    description="Messages sent by this webhook have not been deleted.",
                )
            )
        else:
            await ctx.prompt(
                embed=discord.Embed(
                    title="Confirmation cancelled",
                    description="Action cancelled or command expired.",
                )
            )


def setup(bot):
    bot.add_cog(Webhooks(bot))
