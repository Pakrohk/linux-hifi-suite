# bash completion for hifi-suite                         -*- shell-script -*-

_hifi_suite() {
    local cur prev words cword
    _init_completion || return

    case $prev in
        vol|volume)
            if [[ "$cur" == *+ || "$cur" == *- ]]; then
                COMPREPLY=()
            else
                COMPREPLY=( $(compgen -W '0 10 20 30 40 50 60 70 80 90 100 mute get' -- "$cur") )
            fi
            return ;;
        enable|disable)
            COMPREPLY=( $(compgen -W 'nc surround surround714 eq ec' -- "$cur") )
            return ;;
        mic-prefer)
            COMPREPLY=( $(compgen -A node -W '$(wpctl status 2>/dev/null | grep -oP "\d+\.\s+\S+" | sed "s/[0-9]*\. //")' -- "$cur") )
            return ;;
        mic-prefer-regex)
            COMPREPLY=( $(compgen -W 'alsa_input.usb-* alsa_input.usb-*' -- "$cur") )
            return ;;
        combine)
            COMPREPLY=( $(compgen -W 'Speakers+Headset' -- "$cur") )
            return ;;
        combine-remove)
            COMPREPLY=( $(compgen -W 'Speakers+Headset' -- "$cur") )
            return ;;
        ee-load)
            local dir="${XDG_CONFIG_HOME:-$HOME/.config}/easyeffects/input"
            if [[ -d "$dir" ]]; then
                COMPREPLY=( $(compgen -W "$(ls "$dir"/*.json 2>/dev/null | xargs -I{} basename {} .json)" -- "$cur") )
            fi
            return ;;
        profile)
            COMPREPLY=( $(compgen -W 'list show create delete' -- "$cur") )
            return ;;
        daemon)
            COMPREPLY=( $(compgen -W 'start stop restart status' -- "$cur") )
            return ;;
    esac

    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W 'vol volume status devices battery scan default enable disable effects mic-prefer mic-prefer-regex mic-rules mic-unprefer combine combine-remove ee-list ee-load ee-start ee-stop auto recommend profile daemon help' -- "$cur") )
    fi
}

complete -F _hifi_suite hifi-suite
