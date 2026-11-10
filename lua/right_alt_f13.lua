-- F13 is the dedicated Chinese key (physical right Alt after Windows remapping).
-- Run before ascii_composer so it works while Rime is in English mode.
local function processor(key, env)
  if key.keycode ~= 0xffca then
    return 2 -- kNoop: preserve every other key's existing processing.
  end
  if not key:release() then
    env.engine.context:set_option("ascii_mode", false)
  end
  return 1 -- kAccepted: consume both F13 press and release.
end

return processor
