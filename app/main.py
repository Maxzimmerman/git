  import sys                                                                                                                                                                                                                                                                 
  from app.commands import COMMANDS

  def main():
      name, *args = sys.argv[1:]
      try:
          cmd_cls = COMMANDS[name]
      except KeyError:                                                                                                                                                                                                                                                         
          raise SystemExit(f"Unknown command: {name}")
      cmd_cls().execute(args)               # mirrors  find_command(cmd).execute(...)                                                                                                                                                                                          
                                                                                                                                                                                                                                                                               
  if __name__ == "__main__":
      main() 