-- Run before ascii_composer: preserve native Shift tap/chord/timeout handling,
-- but commit the raw input that set_ascii_mode would otherwise discard.
local M = {}
-- librime-lua caches this module in one Lua VM shared by the input sessions.
-- Remember only the language, never another application's pending input.
local shared_ascii
local sessions = {}

local function sync_mode(env, value)
  env.pending_code = nil
  env.syncing = true
  env.engine.context:set_option("ascii_mode", value)
  env.syncing = false
end

function M.init(env)
  env.ready = false
  sessions[env] = true
  env.connection = env.engine.context.option_update_notifier:connect(function(ctx, name)
    if name ~= "ascii_mode" or env.syncing then
      return
    end
    if not env.ready then
      -- Schema defaults are applied after processor initialization. A new or
      -- reloaded session must inherit, rather than reset, the shared language.
      if shared_ascii ~= nil then
        sync_mode(env, shared_ascii)
      end
      return
    end
    if ctx:get_option("ascii_mode") and env.pending_code then
      local code = env.pending_code
      env.pending_code = nil
      env.engine:commit_text(code)
    end
    shared_ascii = ctx:get_option("ascii_mode")
    for other in pairs(sessions) do
      if other ~= env then
        sync_mode(other, shared_ascii)
      end
    end
  end)
  if shared_ascii ~= nil then
    sync_mode(env, shared_ascii)
  end
end

function M.fini(env)
  sessions[env] = nil
  env.connection:disconnect()
end

function M.func(key, env)
  local ctx = env.engine.context
  env.pending_code = nil
  if shared_ascii == nil then
    shared_ascii = ctx:get_option("ascii_mode")
  elseif ctx:get_option("ascii_mode") ~= shared_ascii then
    sync_mode(env, shared_ascii)
  end
  env.ready = true
  if key.keycode == 0xffe1 and key:release() and not ctx:get_option("ascii_mode")
      and ctx:is_composing() then
    -- ascii_composer clears the composition before notifying the mode change.
    -- No notification occurs for a chord, a long hold, or an English-mode tap.
    env.pending_code = ctx.input
  end
  if key.keycode ~= 0xffca then
    return 2 -- kNoop: preserve every other key's existing processing.
  end
  if not key:release() then
    ctx:set_option("ascii_mode", false)
  end
  return 1 -- kAccepted: consume both F13 press and release.
end

return M
