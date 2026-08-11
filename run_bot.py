#!/usr/bin/env python3
"""
Discord Command Bot for Arcane Portal
Listens for commands in Discord channels and triggers system actions.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ArcaneDiscordBot")

# Safety Check: If bot token is not configured, exit gracefully with code 0.
# This prevents Railway deployment crashes if the user hasn't added the token.
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not BOT_TOKEN:
    logger.warning("=" * 70)
    logger.warning("⚠️ DISCORD_BOT_TOKEN environment variable is not configured.")
    logger.warning("The Discord Command Bot is currently DISABLED.")
    logger.warning("To enable the bot, please create a Bot in the Discord Developer Portal,")
    logger.warning("enable Message Content Intent under the Bot tab, and add the token to .env/Railway.")
    logger.warning("=" * 70)
    sys.exit(0)

try:
    import discord
    from discord.ext import commands
except ImportError:
    logger.error("discord.py package is not installed. Please run pip install discord.py")
    sys.exit(1)

# Initialize bot with default intents + message content
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    logger.info(f"🟢 Discord Bot is online! Logged in as: {bot.user.name} ({bot.user.id})")
    # Set status
    activity = discord.Activity(type=discord.ActivityType.listening, name="!help for commands")
    await bot.change_presence(activity=activity)

@bot.command(name="help")
async def bot_help(ctx):
    """Displays the bot help menu"""
    embed = discord.Embed(
        title="🔮 Arcane Portal Bot - Commands",
        description="Interact with the Arcane Portal system using the prefix `!`.",
        color=0x9B59B6,
        timestamp=ctx.message.created_at
    )
    embed.add_field(
        name="⚡ `!radar`",
        value="Trigger the Arcane Trade Radar. Evaluates distance-to-SL and R-multiple drift for active signals.",
        inline=False
    )
    embed.add_field(
        name="🔍 `!conditions`",
        value="View current market regime decision, altcoin correlation caps, circuit breaker state, and volatility.",
        inline=False
    )
    embed.add_field(
        name="🧠 `!optimizer`",
        value="Trigger an on-demand auto-optimizer run to adjust signal confidence thresholds.",
        inline=False
    )
    embed.add_field(
        name="📅 Daily Check Controls",
        value="• `!brief` - Trigger Morning Trading Brief & Regime Prediction\n"
              "• `!afternoon` - Trigger Afternoon Regime Verification\n"
              "• `!evening` - Trigger EOD Summary & Outlook",
        inline=False
    )
    embed.set_footer(text="Arcane Portal V2 Bot")
    await ctx.send(embed=embed)

@bot.command(name="radar")
async def trigger_radar(ctx):
    """Trigger the Trade Radar manually"""
    await ctx.message.add_reaction("🔄")
    msg = await ctx.send("🔄 Triggering Arcane Trade Radar...")
    
    if not os.getenv("DISCORD_WEBHOOK_URL"):
        await ctx.message.add_reaction("⚠️")
        await msg.edit(content="⚠️ Warning: `DISCORD_WEBHOOK_URL` is not configured in this bot's environment variables. Webhook alerts cannot be posted.")
        return
        
    try:
        from trade_radar import run_trade_radar
        loop = asyncio.get_running_loop()
        # Run blocking execution inside standard thread pool executor
        did_post = await loop.run_in_executor(None, run_trade_radar)
        if did_post:
            await ctx.message.add_reaction("✅")
            await msg.edit(content="✅ Trade Radar run completed and alert posted successfully!")
        else:
            await ctx.message.add_reaction("ℹ️")
            await msg.edit(content="ℹ️ Trade Radar run complete. (Nothing to post or no active signals).")
    except Exception as e:
        await ctx.message.add_reaction("❌")
        await msg.edit(content=f"❌ Error running Trade Radar: `{e}`")

@bot.command(name="conditions")
async def show_conditions(ctx):
    """Display real-time database settings and market conditions"""
    await ctx.message.add_reaction("🔄")
    try:
        from detection.datastore import MangoDataStore
        import json
        
        datastore = MangoDataStore()
        regime = datastore.get_setting("DAILY_REGIME_DECISION", "N/A")
        morning_pred = datastore.get_setting("DAILY_REGIME_MORNING_PRED", "N/A")
        cb_active = datastore.get_setting("CIRCUIT_BREAKER_ACTIVE", "False")
        correlation_cap = datastore.get_setting("MAX_CRYPTO_SAME_DIRECTION", "2")
        
        # Get cached mango indicators
        mango_data_str = datastore.get_setting("MANGO_DASHBOARD_CACHED_DATA")
        btc_vol = "N/A"
        market_trend = "N/A"
        badge_ratio = "N/A"
        
        if mango_data_str:
            try:
                cached = json.loads(mango_data_str)
                btc_data = cached.get('assets', {}).get('BTC', {})
                btc_vol = f"{float(btc_data.get('volatility', 50.0)):.0f}"
                trend_val = cached.get('global_market_trend', 0)
                market_trend = "LONG" if trend_val == 1 else ("SHORT" if trend_val == -1 else "NEUTRAL")
                badge_ratio = f"{cached.get('mango_badge_trend_ratio', 0.5):.0%}"
            except Exception:
                pass
                
        embed = discord.Embed(
            title="🔍 Current Market Conditions",
            color=0x3498DB,
            timestamp=ctx.message.created_at
        )
        embed.add_field(name="Daily Regime Decision", value=f"`{regime}`", inline=True)
        embed.add_field(name="Morning Prediction", value=f"`{morning_pred}`", inline=True)
        embed.add_field(name="Circuit Breaker Active", value=f"`{cb_active}`", inline=True)
        embed.add_field(name="Altcoin Correlation Cap", value=f"`{correlation_cap} position(s)`", inline=True)
        embed.add_field(name="Bitcoin Volatility (BBWP)", value=f"`{btc_vol}`", inline=True)
        embed.add_field(name="Mango Market Trend", value=f"`{market_trend}`", inline=True)
        embed.add_field(name="Active Badge Ratio", value=f"`{badge_ratio}`", inline=True)
        embed.set_footer(text="Arcane Portal Status Engine")
        
        await ctx.message.add_reaction("✅")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.message.add_reaction("❌")
        await ctx.send(f"❌ Error fetching market conditions: `{e}`")

@bot.command(name="optimizer")
async def trigger_optimizer(ctx):
    """Trigger the auto-optimizer manually"""
    await ctx.message.add_reaction("🔄")
    msg = await ctx.send("🔄 Initiating Auto-Optimizer run (recalculating confidence thresholds)...")
    try:
        from auto_optimizer import AutoOptimizer
        optimizer = AutoOptimizer()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, optimizer.run_optimization)
        await ctx.message.add_reaction("✅")
        await msg.edit(content="✅ Auto-Optimizer run completed successfully! Updated confidence settings.")
    except Exception as e:
        await ctx.message.add_reaction("❌")
        await msg.edit(content=f"❌ Error running Auto-Optimizer: `{e}`")

@bot.command(name="research", aliases=["strategy"])
async def trigger_researcher(ctx):
    """Trigger Autonomous Strategy Researcher & Evolutionary Engine manually"""
    await ctx.message.add_reaction("🔄")
    msg = await ctx.send("🔬 Initiating Autonomous Strategy Research & Walk-Forward Optimization...")
    try:
        from strategy_researcher import StrategyResearcher
        researcher = StrategyResearcher()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, researcher.run_research)
        await ctx.message.add_reaction("✅")
        await msg.edit(content="✅ Autonomous Strategy Research cycle completed! Check Discord for evolutionary report.")
    except Exception as e:
        await ctx.message.add_reaction("❌")
        await msg.edit(content=f"❌ Error running Strategy Researcher: `{e}`")

@bot.command(name="brief")
async def trigger_morning_brief(ctx):
    """Trigger Morning Trading Brief manually"""
    await ctx.message.add_reaction("🔄")
    msg = await ctx.send("🔄 Triggering Morning Trading Brief & Regime Prediction...")
    
    if not os.getenv("DISCORD_WEBHOOK_URL"):
        await ctx.message.add_reaction("⚠️")
        await msg.edit(content="⚠️ Warning: `DISCORD_WEBHOOK_URL` is not configured in this bot's environment variables. Webhook alerts cannot be posted.")
        return
        
    try:
        from detection.daily_regime import execute_daily_regime_check
        from detection.datastore import MangoDataStore
        datastore = MangoDataStore()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, execute_daily_regime_check, datastore, False, False)
        await ctx.message.add_reaction("✅")
        await msg.edit(content="✅ Morning Trading Brief sent to Discord channel!")
    except Exception as e:
        await ctx.message.add_reaction("❌")
        await msg.edit(content=f"❌ Error running Morning Brief: `{e}`")

@bot.command(name="afternoon")
async def trigger_afternoon_check(ctx):
    """Trigger Afternoon Verification manually"""
    await ctx.message.add_reaction("🔄")
    msg = await ctx.send("🔄 Triggering Afternoon Regime Verification...")
    
    if not os.getenv("DISCORD_WEBHOOK_URL"):
        await ctx.message.add_reaction("⚠️")
        await msg.edit(content="⚠️ Warning: `DISCORD_WEBHOOK_URL` is not configured in this bot's environment variables. Webhook alerts cannot be posted.")
        return
        
    try:
        from detection.daily_regime import execute_daily_regime_check
        from detection.datastore import MangoDataStore
        datastore = MangoDataStore()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, execute_daily_regime_check, datastore, True, False)
        await ctx.message.add_reaction("✅")
        await msg.edit(content="✅ Afternoon Regime Verification sent to Discord channel!")
    except Exception as e:
        await ctx.message.add_reaction("❌")
        await msg.edit(content=f"❌ Error running Afternoon Verification: `{e}`")

@bot.command(name="evening")
async def trigger_evening_check(ctx):
    """Trigger Evening EOD Summary manually"""
    await ctx.message.add_reaction("🔄")
    msg = await ctx.send("🔄 Triggering Evening End of Day Summary & Outlook...")
    
    if not os.getenv("DISCORD_WEBHOOK_URL"):
        await ctx.message.add_reaction("⚠️")
        await msg.edit(content="⚠️ Warning: `DISCORD_WEBHOOK_URL` is not configured in this bot's environment variables. Webhook alerts cannot be posted.")
        return
        
    try:
        from detection.daily_regime import execute_daily_regime_check
        from detection.datastore import MangoDataStore
        datastore = MangoDataStore()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, execute_daily_regime_check, datastore, False, True)
        await ctx.message.add_reaction("✅")
        await msg.edit(content="✅ Evening EOD Summary sent to Discord channel!")
    except Exception as e:
        await ctx.message.add_reaction("❌")
        await msg.edit(content=f"❌ Error running Evening Summary: `{e}`")

if __name__ == "__main__":
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start Discord Bot client: {e}")
        sys.exit(1)
