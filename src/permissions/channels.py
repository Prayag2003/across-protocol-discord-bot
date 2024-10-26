import discord

def get_admin_overwrites(guild):
    """Get channel permission overwrites for admins and owner"""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.owner: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    
    # Add admin roles
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
    return overwrites