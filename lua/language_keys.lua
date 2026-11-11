-- Run before ascii_composer: preserve native Shift tap/chord/timeout handling,
-- but commit the raw input that set_ascii_mode would otherwise discard.
local M = {}

function M.init(env)
  env.connection = env.engine.context.option_update_notifier:connect(function(ctx, name)
    if name == "ascii_mode" and ctx:get_option("ascii_mode") and env.pending_code then
      local code = env.pending_code
      env.pending_code = nil
      env.engine:commit_text(code)
    end
  end)
end

function M.fini(env)
  env.connection:disconnect()
end

function M.func(key, env)
  local ctx = env.engine.context
  env.pending_code = nil
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
