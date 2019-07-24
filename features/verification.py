import random
import smtplib
import ssl
import string

import discord
from discord.ext.commands import Bot

import utils
from config.config import Config
from config.messages import Messages
from features.base_feature import BaseFeature
from repository.user_repo import UserRepository


class Verification(BaseFeature):

    def __init__(self, bot: Bot, user_repository: UserRepository):
        super().__init__(bot)
        self.repo = user_repository

    def send_mail(self, receiver_email, contents):
        password = Config.email_pass
        port = Config.email_smtp_port
        context = ssl.create_default_context()
        sender_email = Config.email_addr
        subject = "FIT Discord verifikace"
        mail_content = 'Subject: {}\n\n{}'.format(subject,
                                                  contents)

        with smtplib.SMTP_SSL(Config.email_smtp_server, port,
                              context=context) as server:
            server.login(Config.email_name, password)
            server.sendmail(sender_email, receiver_email, mail_content)

    async def send_code(self, message):
        if len(str(message.content).split(" ")) != 2:
            await message.channel.send(Messages.verify_send_format)
            return

        # Check if the user doesn't have the verify role
        if Config.verification_role not in message.author.roles:
            login = str(message.content).split(" ")[1]

            # Some of them will use 'xlogin00' as stated in help,
            # cuz they dumb
            if login == "xlogin00":
                guild = self.bot.get_guild(Config.guild_id)
                fp = await guild.fetch_emoji(585915845146968093)
                await message.channel.send(
                    Messages.verify_send_dumbshit
                    .format(emote=str(fp),
                            user=utils.generate_mention(
                        message.author.id)
                    )
                )
                return

            # Check if the login we got is in the database
            if self.repo.has_unverified_login(login):
                # Generate a verification code
                code = ''.join(random.choices(string.ascii_uppercase +
                                              string.digits, k=20))

                email_message = "!verify " + login + " " + code

                self.send_mail(login + "@stud.fit.vutbr.cz", email_message)

                # Save the newly generated code into the database
                self.repo.save_sent_code(message, code)

                await message.channel.send(
                    Messages.verify_send_success
                    .format(user=utils.generate_mention(
                        message.author.id)))
            else:
                await message.channel.send(
                    Messages.verify_send_not_found
                    .format(user=utils.generate_mention(
                        message.author.id),
                        toaster=utils.generate_mention(
                        Config.admin_id)))
        else:
            await message.channel.send(
                Messages.verify_already_verified
                .format(user=utils.generate_mention(
                    message.author.id),
                    toaster=utils.generate_mention(
                    Config.admin_id)
                )
            )
        try:
            await message.delete()
        except discord.errors.Forbidden:
            return

    @staticmethod
    def transform_year(raw_year: str):
        """Parses year string originally from /etc/passwd into a role name"""
        raw_year_parts = raw_year.split()
        year = None

        if len(raw_year_parts) == 3:
            if raw_year_parts[0] == "FIT":
                raw_year_parts[2] = int(raw_year_parts[2][:-1])  # rip types
                if raw_year_parts[1] == "BIT":
                    year = "BIT"
                    if raw_year_parts[2] < 4:
                        year = str(raw_year_parts[2]) + year
                    else:
                        year = "4BIT+"
                elif raw_year_parts[1] in ["MBS", "MBI", "MIS", "MIN",
                                           "MMI", "MMM", "MGM", "MGMe",
                                           "MPV", "MSK"]:
                    year = "MIT"
                    if raw_year_parts[2] < 3:
                        year = str(raw_year_parts[2]) + year
                    else:
                        year = "3MIT+"
                elif raw_year_parts[1] == "DVI4":
                    year = "PhD+"
            elif raw_year_parts[0] == "FEKT":
                year = "FEKT"

        return year

    async def verify(self, message):
        """"Verify if VUT login is from database"""
        if len(str(message.content).split(" ")) != 3:
            await message.channel.send(Messages.verify_verify_format)
            return

        login = str(message.content).split(" ")[1]
        code = str(message.content).split(" ")[2]

        # Check if the user doesn't have the verify role
        # otherwise they wouldn't need to verify, right?
        if Config.verification_role not in message.author.roles:
            # Some of them will use 'xlogin00' as stated in help
            # yet again, cuz they dumb
            if login == "xlogin00":
                guild = self.bot.get_guild(Config.guild_id)
                fp = await guild.fetch_emoji(585915845146968093)
                await message.channel.send(
                    Messages.verify_send_dumbshit
                    .format(emote=str(fp),
                            user=utils.generate_mention(
                        message.author.id)
                    )
                )
                return
            # Same here
            if code == "kód" or code == "[kód]":
                guild = self.bot.get_guild(Config.guild_id)
                fp = await guild.fetch_emoji(585915845146968093)
                await message.channel.send(
                    Messages.verify_verify_dumbshit
                    .format(emote=str(fp),
                            user=utils.generate_mention(
                        message.author.id)
                    )
                )
                return

            new_user = self.repo.get_user(login)
            # Check the code
            if code != new_user[2]:
                await message.channel.send(
                    Messages.verify_verify_wrong_code
                    .format(user=utils.generate_mention(
                        message.author.id)))
                return

            if new_user is not None:
                # Try and transform the year into the role name
                year = self.transform_year(new_user[1])

                if year is None:
                    await message.channel.send(
                        Messages.verify_verify_manual
                        .format(user=utils.generate_mention(
                            message.author.id),
                            toaster=utils.generate_mention(
                            Config.admin_id),
                            year=str(new_user[1])))
                    return

                try:
                    # Get server verify role
                    verify = discord.utils.get(
                        message.guild.roles,
                        name=Config.verification_role)
                    year = discord.utils.get(message.guild.roles, name=year)
                    member = message.author
                except AttributeError:
                    # jsme v PM
                    guild = self.bot.get_guild(Config.guild_id)
                    verify = discord.utils.get(
                        guild.roles,
                        name=Config.verification_role)
                    year = discord.utils.get(guild.roles, name=year)
                    member = guild.get_member(message.author.id)

                await member.add_roles(verify)
                await member.add_roles(year)

                self.repo.save_verified(login, message.author.name,
                                        message.author.id)

                await message.channel.send(
                    Messages.verify_verify_success
                    .format(user=utils.generate_mention(
                        message.author.id)
                    )
                )
            else:
                await message.channel.send(
                    Messages.verify_verify_not_found
                    .format(user=utils.generate_mention(
                        message.author.id),
                        toaster=utils.generate_mention(
                        Config.admin_id)))
        else:
            await message.channel.send(
                Messages.verify_already_verified
                .format(user=utils.generate_mention(
                    message.author.id),
                    toaster=utils.generate_mention(
                    Config.admin_id)
                )
            )
        try:
            await message.delete()
        except discord.errors.Forbidden:
            return