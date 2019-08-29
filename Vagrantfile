# -*- mode: ruby -*-
# vi: set ft=ruby :

#ENV['VAGRANT_DEFAULT_PROVIDER'] = 'libvirt'

Vagrant.configure("2") do |config|
  ##### DEFINE VM #####
  config.vm.define "wgserver" do |config|
    config.vm.hostname = "wgserver"
    config.vm.box = "generic/ubuntu1804"
    config.vm.box_check_update = false
  end
  config.vm.provision "shell" do |s|
    ssh_pub_key = File.readlines("#{Dir.home}/.ssh/id_rsa.pub").first.strip
    s.inline = <<-SHELL
      echo #{ssh_pub_key} >> /home/vagrant/.ssh/authorized_keys
    SHELL
  end
end
