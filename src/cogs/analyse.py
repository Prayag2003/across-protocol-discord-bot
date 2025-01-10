import discord
from discord.ext import commands
from datetime import datetime, timedelta
from collections import Counter
from loguru import logger
from services.mongo import MongoService

class AnalyseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mongo_service = MongoService()

    @commands.command(name='analyse')
    @commands.has_permissions(administrator=True)
    async def analyse(self, ctx):
        """Generate enhanced analytics report with both embed and downloadable format."""
        try:
            start_date = datetime.utcnow() - timedelta(days=7)
            end_date = datetime.utcnow()

            # Query for logs
            logs = list(self.mongo_service.logs_collection.find({
                "$or": [
                    {"timestamp": {"$gte": start_date, "$lte": end_date}},
                    {"timestamp": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}}
                ]
            }))

            logger.info(f"{len(logs)} logs found for Analysis")
            
            if not logs:
                await ctx.send("No data found for the last 7 days.")
                return
                
            # Collect analytics data
            topics_counter = Counter()
            tags_counter = Counter()
            users_counter = Counter()
            
            for log in logs:
                users_counter[log.get("username", "unknown")] += 1
                for topic in log.get("topics", []):
                    topics_counter[topic] += 1
                for tag in log.get("tags", []):
                    tags_counter[tag] += 1
            
            # Calculate statistics
            total_queries = sum(users_counter.values())
            avg_queries_per_day = total_queries / 7
            queries_with_topics = sum(1 for log in logs if log.get("topics"))
            queries_with_tags = sum(1 for log in logs if log.get("tags"))

            # Create the main embed with improved styling
            main_embed = discord.Embed(
                title="📊 Analytics Report",
                description=f"Statistics for the period: `{start_date.strftime('%Y-%m-%d')}` to `{end_date.strftime('%Y-%m-%d')}`",
                color=0x5865F2  # Discord Blurple color
            )

            # General statistics with improved formatting
            stats_text = (
                "```ansi\n"
                f"\u001b[1;37mTotal Queries:\u001b[0m {total_queries:,}\n"
                f"\u001b[1;37mDaily Average:\u001b[0m {avg_queries_per_day:.1f}\n"
                f"\u001b[1;37mWith Topics:\u001b[0m   {queries_with_topics:,}\n"
                f"\u001b[1;37mWith Tags:\u001b[0m     {queries_with_tags:,}\n"
                "```"
            )
            main_embed.add_field(
                name="📈 General Statistics",
                value=stats_text,
                inline=False
            )

            # Format top topics with numbers and emojis
            top_topics = "\n".join(
                f"`{count:3d}` {topic}" 
                for topic, count in topics_counter.most_common(5)
            )
            main_embed.add_field(
                name="🎯 Top Topics",
                value=top_topics or "No topics found",
                inline=True
            )

            # Format top tags with numbers and emojis
            top_tags = "\n".join(
                f"`{count:3d}` {tag}"
                for tag, count in tags_counter.most_common(5)
            )
            main_embed.add_field(
                name="🏷️ Top Tags",
                value=top_tags or "No tags found",
                inline=True
            )

            # Create the users embed with improved styling
            users_embed = discord.Embed(
                title="👥 User Activity",
                color=0x5865F2
            )

            user_stats = (
                "```ansi\n"
                + "\n".join(
                    f"\u001b[1;37m{queries:3d}\u001b[0m {user}"  # Numbers in bright white color
                    for user, queries in users_counter.most_common(5)
                )
                + "\n```"
            )

            users_embed.add_field(
                name="Most Active Users",
                value=user_stats if user_stats.strip() else "No user activity",
                inline=False
            )

            footer_text = f"Generated at {end_date.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            main_embed.set_footer(text=footer_text)

            await ctx.send(embed=main_embed)
            await ctx.send(embed=users_embed)

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            await ctx.send(f"An error occurred while generating the report: {str(e)}")

async def setup(bot):
    await bot.add_cog(AnalyseCog(bot))