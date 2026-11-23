return function(key, env)
  local context = env.engine.context
  if key:repr() ~= "asciitilde" or not context:get_option("ascii_mode") or context:is_composing() then
    return 2
  end
  env.engine:commit_text("~")
  return 1
end
