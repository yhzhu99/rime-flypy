return function(key, env)
  if key:repr() ~= "asciitilde" then
    return 2
  end
  local context = env.engine.context
  if context:is_composing() then
    context:commit()
  end
  env.engine:commit_text("~")
  return 1
end
